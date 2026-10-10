"""Dev-only: convert the YAMNet Keras h5 weights into the compact numpy model used by the app.

BatchNorm is folded into the convolutions; weights are stored as float16 (~7.5 MB).

    curl -LO https://storage.googleapis.com/audioset/yamnet.h5
    python tools/build_yamnet_npz.py yamnet.h5 clustersound/models/yamnet.npz
"""
import sys

import h5py
import numpy as np

BN_EPS = 1e-4  # yamnet params.batchnorm_epsilon
# (kind, stride) as in yamnet.py _YAMNET_LAYER_DEFS
LAYERS = [("conv", 2), ("sep", 1), ("sep", 2), ("sep", 1), ("sep", 2), ("sep", 1), ("sep", 2)] + \
         [("sep", 1)] * 5 + [("sep", 2), ("sep", 1)]


def main(h5_path: str, out_path: str) -> None:
    f = h5py.File(h5_path, "r")

    def w(path):
        return np.asarray(f[path], dtype=np.float64)

    def fold(prefix, kernel_last_is_out=True):
        beta = w(f"{prefix}/bn/{prefix}/bn/beta:0")
        mean = w(f"{prefix}/bn/{prefix}/bn/moving_mean:0")
        var = w(f"{prefix}/bn/{prefix}/bn/moving_variance:0")
        scale = 1.0 / np.sqrt(var + BN_EPS)  # BN has no gamma (scale=False)
        return scale, beta - mean * scale

    out = {}
    for i, (kind, stride) in enumerate(LAYERS, start=1):
        if kind == "conv":
            p = f"layer{i}/conv"
            k = w(f"{p}/{p}/kernel:0")  # [3,3,1,32] HWIO
            s, b = fold(p)
            out[f"l{i}_conv_w"] = (k * s)[:, :, 0, :]  # [3,3,32]
            out[f"l{i}_conv_b"] = b
        else:
            p = f"layer{i}/depthwise_conv"
            k = w(f"{p}/{p}/depthwise_kernel:0")[:, :, :, 0]  # [3,3,C]
            s, b = fold(p)
            out[f"l{i}_dw_w"] = k * s
            out[f"l{i}_dw_b"] = b
            p = f"layer{i}/pointwise_conv"
            k = w(f"{p}/{p}/kernel:0")[0, 0]  # [Cin, Cout]
            s, b = fold(p)
            out[f"l{i}_pw_w"] = k * s
            out[f"l{i}_pw_b"] = b
        out[f"l{i}_stride"] = np.array(stride)
    out["logits_w"] = w("logits/logits/kernel:0")
    out["logits_b"] = w("logits/logits/bias:0")
    out = {k: (v.astype(np.float16) if v.dtype.kind == "f" else v) for k, v in out.items()}
    np.savez_compressed(out_path, **out)
    print("saved", out_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
