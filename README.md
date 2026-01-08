#  Grammar-Preserving Text Saliency Modulation (GP-TSM)
**[An AI-Resilient Text Rendering Technique for Reading and Skimming Documents](https://www.ziweigu.com/assets/data/gptsm.pdf)**  
Ziwei Gu, Ian Arawjo, Kenneth Li, Jonathan K. Kummerfeld, Elena L. Glassman\
In *the 2024 ACM CHI conference on Human Factors in Computing Systems*\
*CHI ’24, May 11–16, 2024, Honolulu, HI, USA* 


**GP-TSM** is an LLM-powered text rendering technique that supports reading and skimming by reifying recursive sentence compression in text saliency. Readers can skip over de-emphasized segments without compromising their reading flow/ comprehension of the text, while still being able to notice and recover from AI suggestions they disagree with.

* Read the **[full paper](https://www.ziweigu.com/assets/data/gptsm.pdf)**.
* Try the live demo **[here](https://gptsm-6b7fc3be6bdb.herokuapp.com/)**.
* For more information, see **[our lab website](https://glassmanlab.seas.harvard.edu/)**.

## Citation
```
@inproceedings{10.1145/3613904.3642699,
author = {Gu, Ziwei and Arawjo, Ian and Li, Kenneth and Kummerfeld, Jonathan K. and Glassman, Elena L.},
title = {An AI-Resilient Text Rendering Technique for Reading and Skimming Documents},
year = {2024},
isbn = {9798400703300},
publisher = {Association for Computing Machinery},
address = {New York, NY, USA},
url = {https://doi.org/10.1145/3613904.3642699},
doi = {10.1145/3613904.3642699},
booktitle = {Proceedings of the CHI Conference on Human Factors in Computing Systems},
articleno = {898},
numpages = {22},
keywords = {human-AI interaction, natural language processing, text visualization},
location = {<conf-loc>, <city>Honolulu</city>, <state>HI</state>, <country>USA</country>, </conf-loc>},
series = {CHI '24}
}
```

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

For backend only, use the get_shortened_paragraph(orig_paragraph, k) function in llm.py or gptsm-lite.py. The latter is an alternative of the original GP-TSM algorithm that runs faster, and is designed for applications that require a high level of responsiveness or interactivity. It achieves higher speed by using smaller values for N and MAX_DEPTH and removing
grammaticality from evaluation, which is a time-consuming metric to compute. However, this may mean that the key grammar-preserving feature can be violated at times. To achieve the best output quality, please use the original version in llm.py.

### Testing

Run the test harness to validate the algorithm on test cases:

```bash
# Run all tests
python3 test_harness.py YOUR_API_KEY

# Run a specific test
python3 test_harness.py YOUR_API_KEY "Legal Test 1"
```

The test harness validates salience relationships in the output and saves results to `test_results.json`. To add new test cases, edit the `load_legal_test_cases()` function in `test_harness.py`. 



## Researchers

|  Name                 | Affiliation                     |
|-----------------------|---------------------------------|
| [Ziwei Gu](https://www.ziweigu.com/)           | Harvard University |
| [Ian Arawjo](https://ianarawjo.com/) | Harvard University |
| [Kenneth Li](https://likenneth.github.io/)    | Harvard University |
| [Jonathan K. Kummerfeld](https://jkk.name/) | University of Sydney |
| [Elena L. Glassman](https://glassmanlab.seas.harvard.edu/glassman.html)        | Harvard University |


## License

See [`LICENSE.md`](LICENSE.md).

## Testcases to be put into a new test harness for UK legal texts

### Original sentence
"This is because the impetus which may lead S to seek to be
registered as the owner of adjacent land which S formerly thought was already his (or hers) will often be the raising by his neighbour O of a dispute as to his ownership, backed up by evidence in support, which destroys S’s belief that it belongs to him, or at least makes his continuing belief unreasonable."

#### Assertions
- "This is because" < salience of "the impetus"
- "S’s belief" > "or at least makes his continuing belief unreasonable"


### Original Sentence
"The question of construction to be decided on this appeal arises because it is common ground that, as a matter of pure grammar, the italicised passage in paragraph 5(4)(c) of Schedule 6 can be read in two ways, which I will call constructions A and B."

#### Assertions
- Max salience of "The question of construction to be decided on this appeal arises because" < salience of "it is common ground"
- Max salience of "the italicised passage in paragraph 5(4)(c) of Schedule 6 can be read in two ways" 
-- >= than max salience of anything else in the sentence
-- > than max salience of "which I will call constructions A and B."

### Original Sentence
"On 20 September 2002 the respondent Mr Brown was registered as proprietor of a substantial piece of rough, undeveloped land lying to the West of The Promenade, Consett, County Durham (“the Brown land”)."

#### Assertions
- Max salience of "On 20 September 2002" < max salience than "the respondent Mr Brown was registered as proprietor" 
- max salience than "the respondent Mr Brown was registered as proprietor" > max salience of "of a substantial piece of rough, undeveloped land lying to the West of The Promenade, Consett, County Durham (“the Brown land”).
- nice to have: max salience of “the Brown land” > "a substantial piece of rough, undeveloped land lying to the West of The Promenade, Consett, County Durham"

### Original Sentence
"On 8 July 2004 the appellants Mr and Mrs Ridley were registered as proprietors of land adjoining part of the Brown land to the North East of it, and also lying to the West of the Promenade, including a dwelling house known as Valley View."

#### Assertions
- Max salience of "On 8 July 2004" < max salience of "the appellants Mr and Mrs Ridley were registered as proprietors of land adjoining part of the Brown land"

### Assertions across previous two sentences
- max salience of "the respondent Mr Brown was registered as proprietor" 
-- == "the appellants Mr and Mrs Ridley were registered as proprietors of land adjoining part of the Brown land"
-- > the max salience of "to the North East of it, and also lying to the West of the Promenade, including a dwelling house known as Valley View."

### Document section relationships

#### Assertions
- max salience of text within the section titled "The Parties’ Submissions" < max salience of other sections' text
-- may require use of UK-specific system prompt