# OCR recognition model

Used by `RapidOcrEngine` in `src/collegedata/parsers/cac_sieve.py` (read by path from this
directory, resolved relative to `pipeline/`; not packaged).

| file | source (https://www.modelscope.cn/models/RapidAI/RapidOCR) | sha256 |
|---|---|---|
| `ch_PP-OCRv5_rec_mobile.onnx` | `onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.onnx` | `5825fc7ebf84ae7a412be049820b4d86d77620f204a041697b0494669b1742c5` |
| `ppocrv5_dict.txt` | `paddle/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile/ppocrv5_dict.txt` | `d1979e9f794c464c0d2e0b70a7fe14dd978e9dc644c0e71f14158cdf8342af1b` |

Licence: Apache-2.0 (PaddleOCR).

Why: rapidocr's default recognition model is simplified-Chinese only and misreads the
traditional characters of the CAC 篩選標準 images (113/114 parsed to almost nothing). PP-OCRv5
supports traditional Chinese. The engine verifies the onnx sha256 at construction.
