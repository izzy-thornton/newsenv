# NewsEnv

A simple Python application with a GUI made for social scientists and media researchers
---

## Features
- Easy-to-use desktop GUI  
- Scrapes news feeds into clean datasets for quant or qual analysis
- Supports basic visualization and reporting
- Spreadsheet output option for analysis
- Customizable search queries and stopwords
---

## Requirements
- **Python 3.13** (recommended)  
- **Poetry** (for depegindency management)  

If you don’t have Poetry installed yet, run:
```bash
pipx install poetry
```
---
## Installation
Clone this repository:
```bash
git clone https://github.com/izzy-thornton/newsenv.git
cd newsenv
```

Install dependencies into a virtual environment:
```bash
poetry install
```

> Note: PySimpleGUI is installed from its official package server. This is already configured in the project’s `pyproject.toml`.
---

## Usage
Run the program with:
```bash
poetry run python news_gui.py
```
###Data Output Format

When you run a query in NewsEnv, results are exported to Excel (.xlsx) or CSV (.csv) files. Each row represents a single news article returned by the query.

**Columns**

-title

--The headline of the article as published.

-pubdate

--The publication date of the article, when available (format: MM/DD/YYYY). This field may be blank if the source does not provide a publication date.

-date_collected

--The exact timestamp when the article was retrieved by NewsEnv (ISO 8601 format with timezone info). This allows reproducibility and shows when the dataset was generated.

-url

--The direct link to the full article.

-summary

--A short text summary or snippet of the article content (as returned by the search service).

-keywords

--Automatically extracted keywords from the article content, stored as a list of terms. These are useful for thematic analysis, quick filtering, or word cloud generation.

-FullText

--The full body text of the article as collected. Use this field for in-depth text analysis, coding, or natural language processing.

**Example Row**

| Column        | Example Value                                                                 |
|---------------|-------------------------------------------------------------------------------|
| **title**     | Taco Bell expands beverage menu with 6 new sips                               |
| **pubdate**   | (blank)                                                                       |
| **date_collected** | 2025-07-17 13:43:59.926                                                  |
| **url**       | https://abcnews.go.com/                                                       |
| **summary**   | Taco Bell launches Refrescas as new premium beverages…                        |
| **keywords**  | ['summer', 'expands', 'menu', 'refrescas', ...]                               |
| **FullText**  | Full article text                  

**Notes on Usage**

-Some fields (like pubdate) may be missing or incomplete depending on the source.
-To ensure reproducibility, always cite both the pubdate (if available) and the date_collected.
-Keyword extraction is automated and may include duplicates, variants, or lowercased terms.
-If running multiple queries, you may want to concatenate exports and use date_collected to filter by time period.

###PDF Report Format

In addition to the CSV/Excel data exports, NewsEnv also generates a PDF summary report. This file provides a quick, human-readable overview of your search results.

Each PDF report includes:

-Title & Metadata

-Report title (“News Coverage Report: Custom Search”)

-Date the report was generated

-The exact search query that produced the results

-Links to the corresponding CSV and XLSX data files

-Total number of articles retrieved

-Keyword Analysis
--A ranked list of the Top 10 Keywords extracted from the collected articles
--Keywords are listed with their frequency counts (e.g., “taco: 676, bell: 573, chicken: 273”)

---



## License
This project is licensed under the **MIT License**.  


MIT License

Copyright (c) 2025 Izzy Thornton

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## 🙌 Contributing
Pull requests are welcome! For major changes, please open an issue first to discuss what you’d like to change.



