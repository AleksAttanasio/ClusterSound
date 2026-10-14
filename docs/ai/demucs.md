# Demucs (Extract stems)

Meta's [Demucs](https://github.com/adefossez/demucs) separates a track into its sources. ClusterSound uses
**`htdemucs_6s`**, the 6-source *Hybrid Transformer* variant: **drums, bass, guitar, piano, vocals, other**.

## The model

*Hybrid Transformer Demucs* combines two U-Net branches, one on the waveform and one on the spectrogram, with a
**cross-domain Transformer** in the middle that makes the two representations talk to each other. The time branch
preserves the transients (drums), the spectral one the tonal parts; the output is the sum of the two branches for
every source.

## How it is used (`sampler/stems.py`)

| Aspect | Choice |
|---|---|
| Installation | `stems` extra (`demucs>=4.0.1`, `torch>=2.1`) |
| Weights | ~55 MB downloaded on first use into `models/demucs` in the data folder (Hugging Face for demucs ≥ 4.1, redirected `torch.hub` for 4.0), with a `.ready` marker; afterwards only from disk, no network |
| Device | CUDA → MPS → CPU; if an operation is missing on the GPU the job goes on on the CPU |
| Process | inside the app process, in a thread; PyTorch imported only when the separation starts |
| Blocks | **60 s** with **2 s** of overlap and a linear crossfade; inside every block `apply_model(split=True, overlap=0.25)` |
| Normalisation | mean and standard deviation of the mono reference, restored at the output |
| Mono | duplicated to stereo for the model, then averaged back |
| Output | one 24-bit WAV per stem; can be cancelled between blocks (partial files are removed) |

## Chosen stems and "Other"

The user ticks only the stems they need; all the sources that are not chosen are **summed into "Other"**. This way
the files produced always add up to the original (up to the model's error) and nothing is lost.

The stems of the whole recording go into `<recording> - stem/`, those of a region into
`ClusterSound Samples/…/stem/`, with the same provenance note as the source. The stem names in the files follow the
interface language.
