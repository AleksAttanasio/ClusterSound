"""Apollo network, for inference only.

Adapted from look2hear/models/apollo.py of https://github.com/JusperLee/Apollo
(Kai Li, Yi Luo, "Apollo: Band-sequence Modeling for High-Quality Audio Restoration", arXiv:2409.08514),
licensed CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/); this file is under the same licence.
Changes: training-only code, the Hugging Face mixin and debug prints removed. Parameter names are unchanged,
so the published checkpoint loads as is.

Imported only by the worker process.
"""
import collections
import typing

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.torch_version import TorchVersion

SR = 44100
ARGS = {"sr": SR, "win": 20, "feature_dim": 256, "layer": 6}  # the published checkpoint


class RMSNorm(nn.Module):
    def __init__(self, dimension, groups=1):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(dimension))
        self.groups = groups
        self.eps = 1e-5

    def forward(self, input):
        B, N, T = input.shape
        x = input.reshape(B, self.groups, -1, T).float()
        x = x * torch.rsqrt(x.pow(2).mean(-2, keepdim=True) + self.eps)
        return x.type_as(input).reshape(B, N, T) * self.weight.reshape(1, -1, 1)


class Roformer(nn.Module):
    """Transformer with rotary positional embedding."""

    def __init__(self, input_size, hidden_size, num_head=8, theta=10000, window=10000, causal=True):
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size // num_head
        self.num_head = num_head
        self.theta = theta
        self.window = window
        cos_freq, sin_freq = self._calc_rotary_emb()
        self.register_buffer("cos_freq", cos_freq)
        self.register_buffer("sin_freq", sin_freq)
        self.causal = causal
        self.input_norm = RMSNorm(self.input_size)
        self.weight = nn.Conv1d(self.input_size, self.hidden_size * self.num_head * 3, 1, bias=False)
        self.output = nn.Conv1d(self.hidden_size * self.num_head, self.input_size, 1, bias=False)
        self.MLP = nn.Sequential(RMSNorm(self.input_size),
                                 nn.Conv1d(self.input_size, self.input_size * 8, 1, bias=False),
                                 nn.SiLU())
        self.MLP_output = nn.Conv1d(self.input_size * 4, self.input_size, 1, bias=False)

    def _calc_rotary_emb(self):
        freq = 1. / (self.theta ** (torch.arange(0, self.hidden_size, 2)[:(self.hidden_size // 2)] / self.hidden_size))
        freq = freq.reshape(1, -1)
        pos = torch.arange(0, self.window).reshape(-1, 1)
        cos_freq = torch.stack([torch.cos(pos * freq)] * 2, -1).reshape(self.window, self.hidden_size)
        sin_freq = torch.stack([torch.sin(pos * freq)] * 2, -1).reshape(self.window, self.hidden_size)
        return cos_freq, sin_freq

    def _add_rotary_sequence(self, feature):
        T, N = feature.shape[-2:]
        f = feature.reshape(-1, T, N)
        sign = torch.tensor([-1, 1], device=feature.device, dtype=feature.dtype)
        neg = (torch.flip(f.reshape(-1, N // 2, 2), [-1]) * sign.reshape(1, 1, 2)).reshape(-1, T, N)
        rope = f * self.cos_freq[:T].unsqueeze(0) + neg * self.sin_freq[:T].unsqueeze(0)
        return rope.reshape(feature.shape)

    def forward(self, input):
        B, _, T = input.shape
        weight = self.weight(self.input_norm(input)).reshape(B, self.num_head, self.hidden_size * 3, T).mT
        Q, K, V = torch.split(weight, self.hidden_size, dim=-1)
        Q, K = self._add_rotary_sequence(Q), self._add_rotary_sequence(K)
        att = F.scaled_dot_product_attention(Q.contiguous(), K.contiguous(), V.contiguous(), is_causal=self.causal)
        output = self.output(att.mT.reshape(B, -1, T)) + input
        gate, z = self.MLP(output).chunk(2, dim=1)
        return output + self.MLP_output(F.silu(gate) * z)


class ConvActNorm1d(nn.Module):
    def __init__(self, in_channel, hidden_channel, kernel=7):
        super().__init__()
        self.conv = nn.Sequential(nn.Conv1d(in_channel, in_channel, kernel, padding=(kernel - 1) // 2, groups=in_channel),
                                  RMSNorm(in_channel),
                                  nn.Conv1d(in_channel, hidden_channel, 1),
                                  nn.SiLU(),
                                  nn.Conv1d(hidden_channel, in_channel, 1))

    def forward(self, input):
        return input + self.conv(input)


class ICB(nn.Module):
    def __init__(self, in_channel, kernel=7):
        super().__init__()
        self.blocks = nn.Sequential(*[ConvActNorm1d(in_channel, in_channel * 4, kernel) for _ in range(3)])

    def forward(self, input):
        return self.blocks(input)


class BSNet(nn.Module):
    def __init__(self, feature_dim, kernel=7):
        super().__init__()
        self.band_net = Roformer(feature_dim, feature_dim, num_head=8, window=100, causal=False)
        self.seq_net = ICB(feature_dim, kernel=kernel)

    def forward(self, input):
        B, nband, N, T = input.shape
        x = self.band_net(input.permute(0, 3, 2, 1).reshape(B * T, -1, nband))  # across bands
        x = x.reshape(B, T, -1, nband).permute(0, 3, 2, 1)
        return self.seq_net(x.reshape(B * nband, -1, T)).reshape(B, nband, -1, T)  # along time


class Apollo(nn.Module):
    """(batch, channels, samples) at 44.1 kHz -> the same shape, restored."""

    def __init__(self, sr: int, win: int, feature_dim: int, layer: int):
        super().__init__()
        self.sr = sr
        self.win = int(sr * win // 1000)
        self.stride = self.win // 2
        self.enc_dim = self.win // 2 + 1
        self.feature_dim = feature_dim
        self.eps = torch.finfo(torch.float32).eps
        bandwidth = int(self.win / 160)  # 80 bands
        self.band_width = [bandwidth] * 79
        self.band_width.append(self.enc_dim - int(np.sum(self.band_width)))
        self.nband = len(self.band_width)
        self.BN = nn.ModuleList([nn.Sequential(RMSNorm(w * 2 + 1), nn.Conv1d(w * 2 + 1, feature_dim, 1))
                                 for w in self.band_width])
        self.net = nn.Sequential(*[BSNet(feature_dim) for _ in range(layer)])
        self.output = nn.ModuleList([nn.Sequential(RMSNorm(feature_dim), nn.Conv1d(feature_dim, w * 4, 1), nn.GLU(dim=1))
                                     for w in self.band_width])

    def _window(self, device):
        return torch.hann_window(self.win, device=device)

    def feature_extractor(self, input):
        B, nch, n = input.shape
        spec = torch.stft(input.view(B * nch, n), n_fft=self.win, hop_length=self.stride,
                          window=self._window(input.device), return_complex=True)
        feats, idx = [], 0
        for i, w in enumerate(self.band_width):
            s = spec[:, idx:idx + w]
            power = (s.abs().pow(2).sum(1) + self.eps).sqrt().unsqueeze(1)
            norm = torch.complex(s.real / power, s.imag / power)
            feats.append(self.BN[i](torch.cat([norm.real, norm.imag, torch.log(power)], 1)))
            idx += w
        return torch.stack(feats, 1)  # B, nband, N, T

    def forward(self, input):
        B, nch, n = input.shape
        feature = self.net(self.feature_extractor(input))
        est = []
        for i, w in enumerate(self.band_width):
            ri = self.output[i](feature[:, i]).view(B * nch, 2, w, -1)
            est.append(torch.complex(ri[:, 0], ri[:, 1]))
        out = torch.istft(torch.cat(est, 1), n_fft=self.win, hop_length=self.stride,
                          window=self._window(input.device), length=n)
        return out.view(B, nch, -1)


def _inert(module: str, name: str) -> type:
    """A do-nothing class standing in for one the checkpoint names, so it unpickles without importing it."""
    cls = type(name, (), {"__new__": lambda c, *a, **k: object.__new__(c),
                          "__setstate__": lambda self, state: setattr(self, "_state", state)})
    cls.__module__, cls.__qualname__ = module, name
    return cls


# The training config (omegaconf) is pickled next to the weights: it's never used, so it loads into inert stubs
# instead of omegaconf, and torch's weights-only unpickler refuses anything else (no code from the file runs).
_SAFE = [_inert("omegaconf.base", "ContainerMetadata"), _inert("omegaconf.base", "Metadata"),
         _inert("omegaconf.dictconfig", "DictConfig"), _inert("omegaconf.listconfig", "ListConfig"),
         _inert("omegaconf.nodes", "AnyNode"), typing.Any, TorchVersion, collections.defaultdict, dict, list, int]


def load(path: str) -> Apollo:
    """The published checkpoint: {"model_name", "state_dict", "model_args", "infos"}."""
    with torch.serialization.safe_globals(_SAFE):
        conf = torch.load(path, map_location="cpu", weights_only=True)
    model = Apollo(**ARGS)
    model.load_state_dict(conf["state_dict"])
    return model.eval()
