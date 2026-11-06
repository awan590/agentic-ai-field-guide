# The Agentic AI Field Guide: companion code

This is the code for *The Agentic AI Field Guide: Build, Evaluate, and Deploy Production AI Agents and Multi-Agent Systems for Real Customers* by Muhammad Ahsan.

Every example runs offline on Python 3.12 or later with the standard library only: no packages, no API key and no network.

## Layout

- `code/ch01` to `code/ch25`: one folder per chapter, named as in the book.
- `code/tests`: one test file per chapter.
- `logs`: the saved runs that the book prints. Two tests compare live output with these files.
- `VERSION`: the date of this edition of the code.

## Run it

```
cd code
python -m unittest discover -s tests
python -m ch16.smoke_test
```

Appendix A of the book lists the command for each chapter.

## Use

Readers may run, change, and reuse this code in their own work. The book's text and figures are not part of this repository and remain under the author's copyright.
