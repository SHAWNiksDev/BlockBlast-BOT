# Score OCR model

`afr.traineddata` is the unmodified Afrikaans model from the official Tesseract
`tessdata` 4.1.0 release. It is used only with a digit whitelist for the game's
score font; it does not select moves or recognize the board.

Source: https://github.com/tesseract-ocr/tessdata/blob/4.1.0/afr.traineddata

SHA-256: `5ec41cebed3f4a178ee9d72e1112ac9a4a38a7b0ddcafb1266d55d9ded452ea9`

License: Apache License 2.0; see `LICENSE`. The model is distributed unchanged.
Keeping this file in the source and portable package makes digit recognition
independent of whichever language packs are installed on the host.
