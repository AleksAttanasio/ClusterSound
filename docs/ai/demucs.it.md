# Demucs (Estrai stem)

[Demucs](https://github.com/adefossez/demucs) di Meta separa un brano nelle sue sorgenti. ClusterSound usa
**`htdemucs_6s`**, la variante *Hybrid Transformer* a 6 sorgenti: **batteria, basso, chitarra, piano, voce, altro**.

## Il modello

*Hybrid Transformer Demucs* combina due rami U-Net, uno sulla forma d'onda e uno sullo spettrogramma, con un
**Transformer cross-domain** al centro che fa dialogare i due rappresentazioni. Il ramo temporale preserva i
transienti (batteria), quello spettrale le parti tonali; l'uscita è la somma dei due rami per ogni sorgente.

## Come viene usato (`sampler/stems.py`)

| Aspetto | Scelta |
|---|---|
| Installazione | extra `stems` (`demucs>=4.0.1`, `torch>=2.1`) |
| Pesi | ~55 MB scaricati al primo uso in `models/demucs` nella cartella dati (Hugging Face per demucs ≥ 4.1, `torch.hub` reindirizzato per la 4.0), con un marcatore `.ready`; poi solo da disco, senza rete |
| Device | CUDA → MPS → CPU; se un'operazione manca sulla GPU il lavoro continua su CPU |
| Processo | nel processo dell'app, in un thread; PyTorch importato solo all'avvio della separazione |
| Blocchi | **60 s** con **2 s** di sovrapposizione e dissolvenza lineare; dentro ogni blocco `apply_model(split=True, overlap=0.25)` |
| Normalizzazione | media e deviazione standard del riferimento mono, ripristinate in uscita |
| Mono | duplicato in stereo per il modello, poi rimediato |
| Uscita | un WAV 24 bit per stem; annullabile tra un blocco e l'altro (i file parziali vengono rimossi) |

## Stem scelti e "Altro"

L'utente spunta solo gli stem che gli servono; tutte le sorgenti non scelte vengono **sommate in "Altro"**. Così i
file prodotti sommati restituiscono sempre l'originale (a meno dell'errore del modello) e niente va perso.

Gli stem della registrazione intera vanno in `<registrazione> - stem/`, quelli di una regione in
`ClusterSound Samples/…/stem/`, con la stessa nota di provenienza della sorgente.
