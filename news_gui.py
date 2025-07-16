import PySimpleGUI as sg
import os
import traceback
from datetime import datetime
from pathlib import Path
from wordcloud import STOPWORDS
import re
import pandas as pd
import json, os, requests
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, quote
from gnews import GNews
from newspaper import Article
from bs4 import BeautifulSoup
import nltk
nltk.download('punkt', quiet=True)
from wordcloud import WordCloud, STOPWORDS
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path
import pandas as pd
from fpdf import FPDF
from pathlib import Path
from PIL import Image
from pathlib import Path
from PIL import Image
import io
from PIL import Image
import io
import traceback
import sys


SEARCH_PRESETS = {
    "All Poverty Topics": '("Poverty" OR "Land loss" OR "Environmental racism" OR "Homelessness" OR "Unhoused" OR "Panhandling" OR "EBT Funding" OR "SNAP benefits" OR "Medicaid" OR "Medicaid funding" OR "Antiabortion movement" OR "Abortion" OR "Reproductive rights" OR "Prenatal care" OR "Elder care")) AND (Alabama OR Florida OR Georgia OR Louisiana OR Mississippi)',
    "Benefits Programs": '("EBT Funding" OR "SNAP benefits" OR "Medicaid" OR "Medicaid funding") AND (Alabama OR Florida OR Georgia OR Louisiana OR Mississippi)',
    "Health": '("Medicaid" OR "Medicaid funding" OR "Antiabortion movement" OR "Abortion" OR "Reproductive rights" OR "Prenatal care" OR "Elder care") AND (Alabama OR Florida OR Georgia OR Louisiana OR Mississippi)',
    "Historic Black Towns": '("Historic Black Towns" OR "Eatonville" OR "Sanderson Railroad") AND (Alabama OR Florida OR Georgia OR Louisiana OR Mississippi)',
    "Housing": '("Land loss" OR "Homelessness" OR "Unhoused" OR "Panhandling") AND (Alabama OR Florida OR Georgia OR Louisiana OR Mississippi)',
    "Water Crisis and Hurricanes": '("Jackson water crisis" OR "Hurricane Katrina") AND (Alabama OR Florida OR Georgia OR Louisiana OR Mississippi)',
    "SPLC Geographic Area": '(Alabama OR Florida OR Georgia OR Louisiana OR Mississippi)',
    "Custom Search": ""  # User-provided input
}

searchterm=""

stopwords = set(STOPWORDS)
stopwords.update([
# Original custom words
"said", "will", "one", "also", "get", "news", "state","year", "new", "grant", "support", "program", "fund","i", "a", "aboard", "about", "above", "abroad", "according", "accordingly", "across","actually", "after", "afterward", "ago", "aha", "ahead", "ahem", "ahh", "alas", "all", "along", "also", "although", "am", "amid", "amidst", "among","amongst", "an", "and", "another", "any", "anybody", "anyone", "anything", "anywhere","apart", "are", "arg", "around", "as", "aside", "at", "aw", "away", "b", "bam","barring", "be", "because", "been", "before", "behind", "being", "below", "beneath","beside", "besides", "between", "beyond", "bingo", "blah", "boo", "both", "briefly", "brrr", "but", "by", "c", "can", "certain", "circa", "concerning","consequently", "considering", "conversely", "could", "d", "despite", "did", "do", "does", "doing", "done", "down", "due", "duh", "during", "e", "each", "eek", "eh", "eight", "eighteen","eighteenth", "eighth", "eightieth", "eighty", "either", "eleven", "eleventh", "encore","enough", "even", "every", "everybody", "everyone", "everything", "everywhere","except", "excluding", "f", "few", "fewer", "fewest", "fifteen","fifteenth", "fifth", "fiftieth", "fifty", "finally", "first", "five", "following", "for","fortieth", "four", "fourteen", "fourteenth", "fourth", "fourty", "from", "further","furthermore", "g", "gadzooks", "gee", "golly", "gosh", "gradually", "h", "had", "haha", "has", "have", "having", "he", "hence", "her", "hers", "herself", "hey","him", "himself", "his", "hmm", "however", "huh", "humph", "hundred", "hundredth", "i", "if", "in", "inside", "instead", "into", "is", "it", "its", "itself", "j","k", "l", "last", "lastly", "later", "least", "less", "lest", "like", "little", "ll", "m","many", "may", "me", "meanwhile", "might", "million", "millionth", "mine", "minus","more", "moreover", "most", "much", "must", "my", "myself", "n", "near", "need", "needed","needing", "needs", "neither", "nevertheless", "next", "nine", "nineteen", "nineteenth","ninetieth", "ninety", "ninth", "no", "nobody", "none", "nonetheless", "nor", "nothing","now", "nowhere", "o", "of", "off", "oh", "ok", "okay", "on", "once", "one", "onto", "opposite", "or", "other", "others", "ouch", "ought", "our", "ours", "ourselves","out", "outside", "over", "ow", "p", "past", "per", "plus", "presently", "prior", "q", "r", "regarding", "round", "s", "save", "second","seven", "seventeen", "seventeenth", "seventh", "seventieth", "seventy", "several","shall", "she", "shh", "should", "similarly", "since", "six", "sixteen","sixteenth", "sixth", "sixtieth", "sixty", "so", "some", "somebody", "something","somewhere", "soon", "still", "subsequently", "such", "t", "ten", "tenth", "than", "that","the", "their", "theirs", "them", "themselves", "thereafter", "therefore", "these","they", "third", "thirteen", "thirteenth", "thirtieth", "thirty", "this", "those","though", "thousand", "thousandth", "three", "through", "throughout", "thus", "till","times", "to", "toward", "towards", "tut-tut", "twelfth", "twelve", "twentieth", "twenty","two", "u", "ugh", "uh-huh", "uh-oh", "ultimately", "under", "underneath", "unless","unlike", "until", "unto", "up", "upon", "us", "v", "various", "ve", "versus", "via", "w", "was", "we", "well", "were", "what", "whatever", "when", "whenever", "where","whereas", "wherever", "which", "whichever", "while", "whilst", "who", "whoa","whoever", "whom", "whomever", "whoops", "whose", "will", "with", "within", "without","worth", "would", "wow", "x", "y", "yeah", "yes", "yet", "yikes", "yippee", "yo", "you","your", "yours", "yourself", "yourselves", "yuck", "z"
])


def get_article_summary(folder: str, topic_key: str, top_n: int = 10):
    xlsx_path = Path(folder) / topic_key / f"News_{topic_key.replace(' ', '_')}.xlsx"
    num_articles = 0
    top_words = []

    if xlsx_path.exists():
        try:
            df = pd.read_excel(xlsx_path)
            num_articles = df.shape[0]
            text = " ".join(df["FullText"].dropna().astype(str))
            stopwords = set(STOPWORDS)
            words = re.findall(r'\b\w{4,}\b', text.lower())
            word_freq = {}
            for word in words:
                if word not in stopwords:
                    word_freq[word] = word_freq.get(word, 0) + 1
            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:top_n]
        except Exception as e:
            print("Error in get_article_summary:", str(e))

    return num_articles, top_words

def run_scraper(save_folder, searchterm, topic_key):
    
    today = datetime.today()
    formatted_date = (today - pd.DateOffset(months=6)).strftime("%Y-%m-%d")
    pathdate = today.strftime("%Y-%m-%d")
    thisis = topic_key
    searchterm += f" after:{formatted_date}"

    save_path = Path(save_folder) / thisis
    save_path.mkdir(parents=True, exist_ok=True)
    os.chdir(save_path)

    print("🔎 Searching Google News...")
    google_news = GNews()
    raw_results = google_news.get_news(searchterm)
    df_results = pd.DataFrame(raw_results).drop_duplicates(subset="url")
    if not df_results.empty and "url" in df_results.columns:
        df_results = df_results[df_results["url"].notna()].reset_index(drop=True)
    else:
        print("⚠️ No data to process or 'url' column missing.")
        return
    if df_results.empty:
        print("⚠️ No articles found.")
        return

    # Decode redirect URLs
    def get_decoding_params(gn_art_id):
        try:
            response = requests.get(f"https://news.google.com/rss/articles/{gn_art_id}")
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            div = soup.select_one("c-wiz > div")
            return {
                "signature": div.get("data-n-a-sg"),
                "timestamp": div.get("data-n-a-ts"),
                "gn_art_id": gn_art_id,
            }
        except Exception:
            return None

    def decode_urls(articles):
        articles_reqs = [
            [
                "Fbv4je",
                f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{art["gn_art_id"]}",{art["timestamp"]},"{art["signature"]}"]',
            ]
            for art in articles if art
        ]
        if not articles_reqs:
            return []
        payload = f"f.req={quote(json.dumps([articles_reqs]))}"
        headers = {"content-type": "application/x-www-form-urlencoded;charset=UTF-8"}
        response = requests.post(
            url="https://news.google.com/_/DotsSplashUi/data/batchexecute",
            headers=headers,
            data=payload,
        )
        response.raise_for_status()
        return [json.loads(res[2])[1] for res in json.loads(response.text.split("\n\n")[1])[:-2]]

    print("🧠 Decoding article URLs...")
    try:
        articles_params = [
            get_decoding_params(urlparse(article["url"]).path.split("/")[-1])
            for article in df_results.to_dict("records")
        ]
        decoded_urls = decode_urls(articles_params)
    except Exception as e:
        print(f"❌ Failed to decode URLs: {e}")
        return

    print("📰 Downloading article content...")
    article_data = []
    for raw_url in decoded_urls:
        try:
            url = str(raw_url).strip()
            if not url.startswith("http"):
                continue
            article = Article(url)
            article.download()
            article.parse()
            article.nlp()
            article_data.append({
                "title": article.title,
                "pubdate": article.publish_date.strftime("%m/%d/%Y") if article.publish_date else None,
                "date_collected": today,
                "url": url,
                "summary": article.summary,
                "keywords": article.keywords,
                "FullText": article.text, })

           
        except Exception as e:
            print(f"⚠️ Skipped: {url}\nReason: {e}")


    if not article_data:
        print("❌ No valid articles were scraped.")
        return

    print("💾 Saving files...")
    articledf = pd.DataFrame(article_data)
    filename_suffix = topic_key.replace(" ", "_")
    csv_path = save_path / f"News_{filename_suffix}.csv"
    xlsx_path = save_path / f"News_{filename_suffix}.xlsx"
    articledf.to_csv(csv_path, index=False, encoding="utf-8-sig")
    
    # Handle append and deduplication
    if values.get("APPEND_SCRAPE") and xlsx_path.exists():
        try:
            existing_df = pd.read_excel(xlsx_path)
            combined_df = pd.concat([existing_df, articledf], ignore_index=True)
            articledf = combined_df.drop_duplicates(subset=["url"])
            print(f"🔄 Appended to existing file. Total rows after deduplication: {len(articledf)}")
        except Exception as e:
            print(f"⚠️ Failed to append to existing file: {e}")
    elif values.get("NEW_SCRAPE") and xlsx_path.exists():
        confirm = sg.popup_yes_no("File already exists. Overwrite?")
        if confirm != "Yes":
            print("❌ Scrape canceled.")
            return

    articledf.to_excel(xlsx_path, index=False)

    print(f"✅ Scraping complete!\nSaved to:\n  - {csv_path}\n  - {xlsx_path}")
    
def generate_wordcloud(folder, topic_key):
    
    filename_suffix = topic_key.replace(" ", "_")
 

    xlsx_path = Path(folder) / topic_key / f"News_{filename_suffix}.xlsx"
    if not xlsx_path.exists():
        print(f"⚠️ Can't find News.xlsx at {xlsx_path}")
        return

    print("🌀 Generating word cloud...")

    df = pd.read_excel(xlsx_path)
    if "FullText" not in df.columns or df["FullText"].dropna().empty:
        print("⚠️ No article text found to generate word cloud.")
        return

    text = " ".join(df["FullText"].dropna().astype(str))

    wc = WordCloud(width=1600, height=800, stopwords=stopwords, background_color="white", colormap="coolwarm").generate(text)

    output_path = Path(folder) / topic_key / f"WordCloud_{filename_suffix}.png"
    wc.to_file(output_path)

    print(f"✅ Word cloud saved to:\n  - {output_path}")


def generate_pdf_report_with_summary(save_folder: str, topic_key: str, search_query: str, top_n_keywords: int = 10):
    folder = Path(save_folder) / topic_key
    wordcloud_path = folder / f"WordCloud_{topic_key.replace(' ', '_')}.png"
    csv_path = folder / f"News_{topic_key.replace(' ', '_')}.csv"
    xlsx_path = folder / f"News_{topic_key.replace(' ', '_')}.xlsx"
    pdf_path = folder / f"NewsReport_{topic_key.replace(' ', '_')}_{pathdate}.pdf"

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"News Coverage Report: {topic_key}", ln=True)

    # Add timestamp and search query
    current_date = datetime.now().strftime("%B %d, %Y")
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Date: {current_date}", ln=True)
    pdf.multi_cell(0, 10, f"Search Query: {search_query}")
    pdf.ln(5)
    
    # Add word cloud image
    if wordcloud_path.exists():
        image = Image.open(wordcloud_path)
        width, height = image.size
        aspect = height / width
        pdf.image(str(wordcloud_path), x=10, y=None, w=180, h=180 * aspect)
        pdf.ln(10)
    else:
        pdf.set_font("Arial", "I", 12)
        pdf.cell(0, 10, "Word cloud image not found.", ln=True)

    pdf.set_font("arial", "", 12)
    pdf.cell(0, 10, f"Topic: {topic_key}", ln=True)
    pdf.cell(0, 10, f"CSV File: {csv_path.name if csv_path.exists() else 'Not found'}", ln=True)
    pdf.cell(0, 10, f"XLSX File: {xlsx_path.name if xlsx_path.exists() else 'Not found'}", ln=True)
    pdf.ln(5)

    # Add summary stats
    if xlsx_path.exists():
        try:
            df = pd.read_excel(xlsx_path)
            num_articles = df.shape[0]
            pdf.cell(0, 10, f"Number of Articles: {num_articles}", ln=True)

            # Top keywords from FullText column
            stopwords = set(STOPWORDS)
            text = " ".join(df["FullText"].dropna().astype(str))
            words = re.findall(r'\b\w{4,}\b', text.lower())
            word_freq = {}
            for word in words:
                if word not in stopwords:
                    word_freq[word] = word_freq.get(word, 0) + 1
            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:top_n_keywords]

            pdf.ln(5)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, f"Top {top_n_keywords} Keywords:", ln=True)
            pdf.set_font("arial", "", 12)
            for word, count in top_words:
                pdf.cell(0, 10, f"{word}: {count}", ln=True)
        except Exception as e:
            pdf.cell(0, 10, f"Error reading data: {str(e)}", ln=True)

    pdf.output(str(pdf_path))
    return str(pdf_path)


def try_generate_and_show_wordcloud(folder, topic_key):
    try:

        generate_wordcloud(folder, topic_key)
        filename_suffix = topic_key.replace(" ", "_")
        wc_path = Path(folder) / topic_key / f"WordCloud_{filename_suffix}.png"

        if wc_path.exists():

            with Image.open(wc_path) as img:
                img = img.resize((800, 400))  # Adjust width and height as needed
                bio = io.BytesIO()
                img.save(bio, format="PNG")
                window["WORDCLOUD"].update(data=bio.getvalue())
                
        else:
            print(f"⚠️ Word cloud file not found at {wc_path}")
    
    except Exception as e:
        print("❌ Error displaying word cloud:")
        traceback.print_exc()
       
#Layout begin
cere=b'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'

sg.theme('Reddit')
FONT = ("Montserrat", 16)
FONT2 = ("Montserrat", 12)
FONT3 = ("Montserrat", 24)
FONT4 = ("Courier", 10)
left_col_top = [
   
[sg.Frame("Search Parameters", [
    [sg.Text("Save folder:", size=(20, 1), font=FONT),
     sg.InputText(key="FOLDER_PATH", size=(30, 1), font=FONT),
     sg.FolderBrowse(font=FONT, tooltip="Choose a folder to save scraped data")],
    
    [sg.Radio("Start new scrape", "MODE", default=True, key="NEW_SCRAPE", font=FONT,
              tooltip="This will overwrite previous results")],
    
    [sg.Radio("Append to existing and deduplicate", "MODE", key="APPEND_SCRAPE", font=FONT,
              tooltip="This will add new articles and remove duplicates")],
    
    [sg.Text("Select topic:", size=(20, 1), font=FONT),
     sg.Combo(list(SEARCH_PRESETS.keys()), default_value="All Poverty Topics", key="TOPIC",
              enable_events=True, size=(29, 1), font=FONT,
              tooltip="Choose a search topic or 'Custom Search'")],
    [sg.Text("Custom search term:",key="CUSTOMTEXT", size=(20, 1), font=FONT, visible=False), sg.InputText(key="CUSTOM", visible=False, size=(30, 2), font=FONT, tooltip="Choose a search topic or 'Custom Search'"),sg.Text("Search query:",key="SEARCHTERMTEXT", size=(20, 1), font=FONT, visible=False),sg.Multiline(searchterm,key="SEARCHTERM", size=(90, 2),font=FONT4, visible=False, no_scrollbar=True, autoscroll=False, background_color='#ffffff', border_width=0)]
], font=FONT, pad=(10, 10), size=(800,200))]
    
]

left_col_scrollable =[
    [sg.Frame("Scraper Output", [
        [sg.Output(expand_x=True, size=(None, 5), font=("Courier", 10), key="OUTPUT",)],
        [sg.Text("", key="SUMMARY_OUTPUT", font=FONT)],
        [sg.Text("Top Keywords Table:", font=FONT)],
        [sg.Table(
            values=[["", ""]] * 10,
            headings=["Keyword", "Count"],
            key="KEYWORDS_TABLE",
            auto_size_columns=True,
            expand_x=True,
            justification="left",
            font=FONT,
            num_rows=10,
            alternating_row_color="#f0f0f0",
            enable_events=False,
            hide_vertical_scroll=True
        )],
        [sg.Text("", size=(20, 1), font=FONT)],
        [sg.Text("Word Cloud:", font=FONT)],
        [sg.Image(key="WORDCLOUD", size=(800, 400))],
        ], font=FONT, pad=(10, 10), size=(800,900))
]]

right_col = [
    [sg.Button("Run Scraper", size=(9, 2), font=FONT, tooltip="Start scraping Google News", button_color=("#ffffff", "#00aa00"))],
    [sg.Button("Generate Report", key="PDF_REPORT", disabled=True, size=(15, 1), font=FONT, disabled_button_color=("gray", "#dcdcdc"), tooltip="Export summary PDF report after scrape is complete")],
    [sg.Button("Clear All", size=(15, 1), font=FONT, tooltip="Clear all fields and reset to defaults")],
    [sg.Button("Help", size=(15, 1), font=FONT, tooltip="Click to view instructions")],
    [sg.Button("Exit", size=(15, 1), button_color=("#ffffff", "#aa0000"), font=FONT, tooltip="Close the application")],
    [sg.Text("", size=(15, 1), font=FONT)],
    [sg.Multiline("Use this tool to compile a sample of news articles related to your search term(s). Articles will be downloaded as a spreadsheet into your selected folder and will include titles, URLs, and keywords. Most articles will also include authors, publication dates, and a copy of the full text of the article. \n\nAfter the program has run, a word cloud and summary statistics are displayed. Optionally, you can download a PDF summary of the findings using the button above.", size=(21, None), disabled=True, font=FONT2, justification='left',no_scrollbar=True, autoscroll=False, background_color='#ffffff', border_width=0,)],
    [sg.Text("", size=(15, 1), font=FONT)],
]

layout = [
        [sg.Image(cere,), sg.Text("News Scrape Utility", size=(None, 2), font=FONT3, expand_x=True, justification='left', pad=((30,0), (30, 0)))],
    [
        sg.Column(
            [
                [sg.Column(left_col_top, pad=(0, 0), element_justification='left', size=(None, None))],
                [sg.Column(left_col_scrollable, scrollable=True, vertical_scroll_only=True, size=(None, 500), pad=(0, 0))]
            ],
            element_justification='left'
        ),
        sg.VSeparator(),
        sg.Column(right_col, element_justification='left', vertical_alignment='top', size=(300, None),expand_y=True)
    ]
]

window = sg.Window("News Scraper", layout, resizable=True, size=(1150, 800))

       
       
       
       
#While Loop
while True:
    event, values = window.read()
    if event in (sg.WIN_CLOSED, "Exit"):
        break
    
    elif event == "Clear All":
        window["FOLDER_PATH"].update("")
        window["NEW_SCRAPE"].update(value=True)
        window["APPEND_SCRAPE"].update(value=False)
        window["TOPIC"].update("All Poverty Topics")
        window["CUSTOM"].update("", visible=False),
        window["CUSTOMTEXT"].update("", visible=False),
        window["SUMMARY_OUTPUT"].update("")
        window["KEYWORDS_TABLE"].update(values=[["", ""]] * 10)
        window["WORDCLOUD"].update(data=None)
        window["PDF_REPORT"].update(disabled=True)
        continue

    if event == "Help":
        sg.popup(
            
            "How to Use the News Scraper Tool",
            "- Choose a folder where your results will be saved.\n"
            "- Select a predefined topic or enter your own custom search.\n"
            "- Click 'Run Scraper' to begin scraping news articles.\n"
            "- Results are automatically saved as .csv and .xlsx in the folder you selected.\n"
            "- Once completed, a word cloud will be displayed and saved.\n"
            "- You can download a pdf summary report after the scrape completes.\n\n"
           
            "The scraper pulls articles from Google News from the past 6 months. Note that publications may vary in how they report the dates and locations of their articles, so geographic and calendar specifications in search queries may not filter results with 100% accuracy.\n\n"
           
            "Why do some articles appear as 'skipped'?\n"
            "The scraper will compile a list of news articles, titles, and URLs. In most cases, it will also download the full text of the article. However, if a paywall, login requirement, or other barrier prevents full text availability, the tool will skip downloading text for that link. The article title and its URL will still appear in the results spreadsheet.\n\n\n\n",
            "Version 1.0, 071525", title="Help", font=FONT)

    if event == "TOPIC":
        topic_key = values["TOPIC"]
        searchterm = SEARCH_PRESETS.get(topic_key)
        window["CUSTOMTEXT"].update(visible=(values["TOPIC"] == "Custom Search"))
        window["CUSTOM"].update(visible=(values["TOPIC"] == "Custom Search"))
        window["SEARCHTERMTEXT"].update(visible=(values["TOPIC"] != "Custom Search"))
        window["SEARCHTERM"].update(searchterm if topic_key != "Custom Search" else "", visible=(topic_key != "Custom Search"))

    if not values or "FOLDER_PATH" not in values or not values["FOLDER_PATH"]:
        print("⚠️ Please select a folder first.")
        continue

    save_folder = values["FOLDER_PATH"]

    if event == "Run Scraper":
        try:
            topic_key = values["TOPIC"]
            if topic_key == "Custom Search":
                searchterm = values["CUSTOM"].strip()
                if not searchterm:
                    print("⚠️ Please enter a custom search term.")
                    continue
            else:
                searchterm = SEARCH_PRESETS.get(topic_key)

            if not searchterm:
                print("⚠️ Invalid or empty search topic.")
                continue

            run_scraper(save_folder, searchterm, topic_key)
            try_generate_and_show_wordcloud(save_folder, topic_key)
            num_articles, top_words = get_article_summary(save_folder, topic_key)
            
            if num_articles == 0:
                window["SUMMARY_OUTPUT"].update("⚠️ No articles found.\nTry checking your query or running the scraper.")
            else:
                summary_text = f"Articles scraped: {num_articles}"
                window["SUMMARY_OUTPUT"].update(summary_text)
                keyword_rows = [[word, count] for word, count in top_words]
                window["KEYWORDS_TABLE"].update(values=keyword_rows)
                window["PDF_REPORT"].update(disabled=False)
                

        except Exception as e:
            print("❌ Error occurred during scraping:")
            traceback.print_exc()
       
    elif event == "Download Word Cloud":
        try:
            topic_key = values["TOPIC"]
            generate_wordcloud(save_folder, topic_key)
        except Exception as e:
            print("❌ Error occurred while generating word cloud:")
            import traceback
            traceback.print_exc()
            
    elif event == "PDF_REPORT":
        try:
            topic_key = values["TOPIC"]
            search_query = values["CUSTOM"] if topic_key == "Custom Search" else SEARCH_PRESETS.get(topic_key, topic_key)
            generate_pdf_report_with_summary(save_folder, topic_key, search_query)

            sg.popup("✅ PDF report generated successfully.", title="Report Complete", font=FONT)
        except Exception as e:
            traceback.print_exc()
            sg.popup_error("❌ Error creating PDF report:", str(e))

window.close()







