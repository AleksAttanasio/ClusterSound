# YAMNet

[YAMNet](https://github.com/tensorflow/models/tree/master/research/audioset/yamnet) è una MobileNet v1 di Google
addestrata su **AudioSet** (521 classi di eventi sonori). In ClusterSound fornisce due cose:

- un **embedding a 1024 dimensioni** per ogni sample: la base di somiglianza, sottocluster, mappa 3D e della head
  di classificazione;
- **score su 521 classi AudioSet**, usati come segnale *zero-shot* (es. *Snare drum*, *Hi-hat*, *Clapping*).

## Front-end log-mel (`frontend.py`)

Riproduce esattamente le feature del modello originale, in numpy:

| Parametro | Valore |
|---|---|
| Frequenza | 16 kHz mono |
| Finestra / hop | 25 ms (400 campioni) / 10 ms (160), Hann periodica, FFT 512 |
| Mel | 64 bande HTK, 125–7500 Hz, `log(mel + 0.001)` |
| Patch | 96 frame × 64 bande (0,96 s), hop di 48 frame (0,48 s) |

Il segnale viene prima normalizzato a picco 0,9 e tagliato a 10 s; il padding garantisce almeno una patch.

## Rete (`yamnet_np.py`)

MobileNet v1 in layout NHWC con padding "SAME" di TensorFlow:

1. conv 3×3 standard, 32 canali, stride 2 (implementata come *im2col* + matmul);
2. 13 blocchi **depthwise-separable**: depthwise 3×3 (nove shift moltiplicati e sommati) + pointwise 1×1
   (matmul BLAS), ReLU dopo ciascuno; stride `[2,1,2,1,2,1,2,1,1,1,1,1,2,1]` sui 14 layer;
3. *global average pooling* → embedding 1024-d;
4. layer lineare 1024 → 521 e sigmoide → score.

La BatchNorm è **fusa nei pesi** in fase di conversione (scala = 1/√(var + 1e-4)), quindi a runtime ci sono solo
moltiplicazioni e somme. I 70 array sono salvati in **float16** (`models/yamnet.npz`, 6,9 MB) e convertiti in
float32 al caricamento; il modello è un singleton caricato alla prima analisi e protetto da un lock.

La conversione dai pesi Keras originali (`yamnet.h5`) è in `tools/build_yamnet_npz.py`.

## Pooling sulle patch (`embedder.py`)

Un sample produce N patch (elaborate a gruppi di 16). Per non far pesare il silenzio o la coda:

- ogni patch ha un peso `softmax(energia log-mel media)`: le patch forti contano di più;
- **embedding** e `scores_mean` = medie pesate; `scores_max` = massimo sulle patch.

Embedding, score e profilo mel vengono salvati in float16 nella cache.

## Come vengono usati

| Uso | Cosa | Dove |
|---|---|---|
| Zero-shot | `0,5·max + 0,5·mean` degli score, mappati sulle classi con pesi (es. Kick ← *Bass drum* 1,0, *Thump* 0,6) | [Classificatore](classificatore.md) |
| Classificazione | embedding L2-normalizzato come input delle head MLP | [Classificatore](classificatore.md) |
| Somiglianza | coseno tra embedding normalizzati (*Trova simili*, Drum Rack) | [Clustering](../algoritmi/clustering-e-mappa.md) |
| Struttura | sottocluster k-means e mappa t-SNE | [Clustering](../algoritmi/clustering-e-mappa.md) |
| Profilo | spettro d'attacco, del corpo e inviluppo ricavati dal log-mel (144 valori) | [Analisi audio](../algoritmi/analisi-audio.md) |
