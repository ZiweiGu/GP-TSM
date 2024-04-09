# GP-TSM
**[An AI-Resilient Text Rendering Technique for Reading and Skimming Documents](https://www.ziweigu.com/assets/data/gptsm.pdf)**  
Ziwei Gu, Ian Arawjo, Kenneth Li, Jonathan K. Kummerfeld, Elena L. Glassman
*The 2024 ACM CHI conference on Human Factors in Computing Systems*
*CHI ’24, May 11–16, 2024, Honolulu, HI, USA* 


**GP-TSM** is an LLM-powered text rendering technique that supports reading and skimming by reifying recursive sentence compression in text saliency. Readers can skip over de-emphasized segments without compromising their reading flow/ comprehension of the text, while still being able to notice and recover from AI suggestions they disagree with.

* Read the **[full paper](https://www.ziweigu.com/assets/data/gptsm.pdf)**.
* **[Cite this work and more](https://www.ziweigu.com/assets/data/gptsm.pdf)**.

![teaser figure](teaser.png)
In this example we show what it looks like when **GP-TSM** is applied to two paragraphs of text from GRE (The Graduate Record Examinations) Practice Exams. **GP-TSM** uses an LLM-based recursive sentence compression method to identify successive levels of detail beyond the core meaning of a passage, which are de-emphasized by rendering words with successively lighter but still legible gray text.


## Installation

Clone the repository:

```
git clone https://github.com/ZiweiGu/GP-TSM
```

Then, set up the virtual environment (called venv) using virtualenv (installation [here](https://virtualenv.pypa.io/en/latest/installation.html)):
```

virtualenv -p python3 venv 
```

Activate the virtual environment:
```

source venv/bin/activate
```

Install necessary packages:
```

pip install -r requirements.txt
```

## Usage

Run the app (in development mode) with:

```
python3 app.py
```


## Researchers

|  Name                 | Affiliation                     |
|-----------------------|---------------------------------|
| [Ziwei Gu](https://www.ziweigu.com/)           | Harvard University |
| [Ian Arawjo](https://ianarawjo.com/) | Harvard University |
| [Kenneth Li](https://likenneth.github.io/)    | Harvard University |
| [Jonathan K. Kummerfeld](https://jkk.name/) | University of Sydney |
| [Elena L. Glassman](https://glassmanlab.seas.harvard.edu/glassman.html)        | Harvard University |

## Citation
```
@misc{gu2024airesilient,
      title={An AI-Resilient Text Rendering Technique for Reading and Skimming Documents}, 
      author={Ziwei Gu and Ian Arawjo and Kenneth Li and Jonathan K. Kummerfeld and Elena L. Glassman},
      year={2024},
      eprint={2401.10873},
      archivePrefix={arXiv},
      primaryClass={cs.HC}
}
```

## License

MIT License. See [`LICENSE.md`](LICENSE.md).
