# YAMNet

[YAMNet](https://github.com/tensorflow/models/tree/master/research/audioset/yamnet) is a Google MobileNet v1
trained on **AudioSet** (521 sound event classes). In ClusterSound it provides two things:

- a **1024-dimensional embedding** for every sample: the basis of similarity, subclusters, 3D map and of the
  classification head;
- **scores on 521 AudioSet classes**, used as a *zero-shot* signal (e.g. *Snare drum*, *Hi-hat*, *Clapping*).

## Log-mel front end (`frontend.py`)

It reproduces exactly the features of the original model, in numpy:

| Parameter | Value |
|---|---|
| Sample rate | 16 kHz mono |
| Window / hop | 25 ms (400 samples) / 10 ms (160), periodic Hann, FFT 512 |
| Mel | 64 HTK bands, 125–7500 Hz, `log(mel + 0.001)` |
| Patch | 96 frames × 64 bands (0.96 s), hop of 48 frames (0.48 s) |

The signal is first normalised to a 0.9 peak and cut at 10 s; padding guarantees at least one patch.

## Network (`yamnet_np.py`)

MobileNet v1 in NHWC layout with TensorFlow "SAME" padding:

1. standard 3×3 conv, 32 channels, stride 2 (implemented as *im2col* + matmul);
2. 13 **depthwise-separable** blocks: 3×3 depthwise (nine shifts multiplied and summed) + 1×1 pointwise
   (BLAS matmul), ReLU after each; strides `[2,1,2,1,2,1,2,1,1,1,1,1,2,1]` on the 14 layers;
3. *global average pooling* → 1024-d embedding;
4. linear layer 1024 → 521 and sigmoid → scores.

BatchNorm is **folded into the weights** at conversion time (scale = 1/√(var + 1e-4)), so at runtime there are only
multiplications and sums. The 70 arrays are saved in **float16** (`models/yamnet.npz`, 6.9 MB) and converted to
float32 on load; the model is a singleton loaded at the first analysis and protected by a lock.

The conversion from the original Keras weights (`yamnet.h5`) is in `tools/build_yamnet_npz.py`.

## Pooling over the patches (`embedder.py`)

A sample produces N patches (processed in groups of 16). So that silence or the tail do not weigh in:

- every patch has a weight `softmax(mean log-mel energy)`: loud patches count more;
- **embedding** and `scores_mean` = weighted means; `scores_max` = maximum over the patches.

Embedding, scores and mel profile are saved in float16 in the cache.

## How they are used

| Use | What | Where |
|---|---|---|
| Zero-shot | `0.5·max + 0.5·mean` of the scores, mapped onto the classes with weights (e.g. Kick ← *Bass drum* 1.0, *Thump* 0.6) | [Classifier](classifier.md) |
| Classification | L2-normalised embedding as the input of the MLP heads | [Classifier](classifier.md) |
| Similarity | cosine between normalised embeddings (*Find similar*, Drum Rack) | [Clustering](../algorithms/clustering-and-map.md) |
| Structure | k-means subclusters and t-SNE map | [Clustering](../algorithms/clustering-and-map.md) |
| Profile | attack spectrum, body spectrum and envelope derived from the log-mel (144 values) | [Audio analysis](../algorithms/audio-analysis.md) |
