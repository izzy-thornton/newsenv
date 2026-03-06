
"""
news_gui_tk.py
Replacement GUI for news_gui.py that removes the proprietary PySimpleGUI dependency.

- Uses only the Python standard library for the GUI (tkinter + ttk).
- Preserves the app's workflow: select folder, choose topic/custom query, run scrape,
  view summary + top keywords table + wordcloud preview, and generate a PDF report.
"""

from __future__ import annotations

import base64
import io
import os
import re
import sys
import json
import queue
import threading
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, quote

import requests
import pandas as pd
import nltk
from bs4 import BeautifulSoup
from gnews import GNews
from newspaper import Article
from fpdf import FPDF
from wordcloud import WordCloud, STOPWORDS
from PIL import Image, ImageTk  # pillow

import tkinter as tk
from tkinter import ttk, filedialog, messagebox


# -----------------------------
# Search presets (unchanged)
# -----------------------------
SEARCH_PRESETS = {
    "All Poverty Topics": '("Poverty" OR "Land loss" OR "Environmental racism" OR "Homelessness" OR "Unhoused" OR "Panhandling" OR "EBT Funding" OR "SNAP benefits" OR "Medicaid" OR "Medicaid funding" OR "Antiabortion movement" OR "Abortion" OR "Reproductive rights" OR "Prenatal care" OR "Elder care")) AND (Alabama OR Florida OR Georgia OR Louisiana OR Mississippi)',
    "Benefits Programs": '("EBT Funding" OR "SNAP benefits" OR "Medicaid" OR "Medicaid funding") AND (Alabama OR Florida OR Georgia OR Louisiana OR Mississippi)',
    "Health": '("Medicaid" OR "Medicaid funding" OR "Antiabortion movement" OR "Abortion" OR "Reproductive rights" OR "Prenatal care" OR "Elder care") AND (Alabama OR Florida OR Georgia OR Louisiana OR Mississippi)',
    "Historic Black Towns": '("Historic Black Towns" OR "Eatonville" OR "Sanderson Railroad") AND (Alabama OR Florida OR Georgia OR Louisiana OR Mississippi)',
    "Housing": '("Land loss" OR "Homelessness" OR "Unhoused" OR "Panhandling") AND (Alabama OR Florida OR Georgia OR Louisiana OR Mississippi)',
    "Water Crisis and Hurricanes": '("Jackson water crisis" OR "Hurricane Katrina") AND (Alabama OR Florida OR Georgia OR Louisiana OR Mississippi)',
    "SPLC Geographic Area": '(Alabama OR Florida OR Georgia OR Louisiana OR Mississippi)',
    "Custom Search": ""
}

# Custom stopwords (kept)
STOPWORDS_CUSTOM = set(STOPWORDS)
STOPWORDS_CUSTOM.update([
    "said", "will", "one", "also", "get", "news", "state", "year", "new",
    "grant", "support", "program", "fund"
])
# (The original file had a very long stopword list that included almost every short word.
# Keeping STOPWORDS (from wordcloud) + a small custom add-on tends to work better in practice.)


# -----------------------------
# Helpers for logging
# -----------------------------
class LogSink:
    """Thread-safe logger: worker threads call .write(str), GUI polls queue and inserts into Text."""
    def __init__(self) -> None:
        self.q: queue.Queue[str] = queue.Queue()

    def write(self, msg: str) -> None:
        if msg:
            self.q.put(msg)

    def flush(self) -> None:
        pass


def _log_default(msg: str) -> None:
    print(msg, flush=True)


# -----------------------------
# Core functionality (refactored slightly)
# -----------------------------
def get_article_summary(folder: str, topic_key: str, top_n: int = 10):
    xlsx_path = Path(folder) / topic_key / f"News_{topic_key.replace(' ', '_')}.xlsx"
    num_articles = 0
    top_words = []

    if xlsx_path.exists():
        try:
            df = pd.read_excel(xlsx_path)
            num_articles = df.shape[0]
            text = " ".join(df.get("FullText", pd.Series(dtype=str)).dropna().astype(str))
            words = re.findall(r"\b\w{4,}\b", text.lower())
            word_freq: dict[str, int] = {}
            for w in words:
                if w not in STOPWORDS_CUSTOM:
                    word_freq[w] = word_freq.get(w, 0) + 1
            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:top_n]
        except Exception:
            # best-effort; don't crash the UI
            pass

    return num_articles, top_words


def run_scraper(
    save_folder: str,
    searchterm: str,
    topic_key: str,
    mode: str,
    *,
    log=_log_default,
) -> None:
    """
    mode:
      - "new": overwrite existing XLSX/CSV
      - "append": append to existing XLSX and deduplicate by url
    """
    today = datetime.today()
    formatted_date = (today - pd.DateOffset(months=6)).strftime("%Y-%m-%d")
    searchterm_with_date = f"{searchterm} after:{formatted_date}"

    save_path = Path(save_folder) / topic_key
    save_path.mkdir(parents=True, exist_ok=True)

    filename_suffix = topic_key.replace(" ", "_")
    csv_path = save_path / f"News_{filename_suffix}.csv"
    xlsx_path = save_path / f"News_{filename_suffix}.xlsx"

    # Scrape list
    log("🔎 Searching Google News...")
    google_news = GNews()
    raw_results = google_news.get_news(searchterm_with_date)
    df_results = pd.DataFrame(raw_results).drop_duplicates(subset="url")
    if not df_results.empty and "url" in df_results.columns:
        df_results = df_results[df_results["url"].notna()].reset_index(drop=True)
    else:
        log("⚠️ No data to process or 'url' column missing.")
        return
    if df_results.empty:
        log("⚠️ No articles found.")
        return

    # Decode redirect URLs (as in original)
    def get_decoding_params(gn_art_id: str):
        try:
            response = requests.get(f"https://news.google.com/rss/articles/{gn_art_id}", timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            div = soup.select_one("c-wiz > div")
            if not div:
                return None
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
            timeout=60,
        )
        response.raise_for_status()
        return [json.loads(res[2])[1] for res in json.loads(response.text.split("\n\n")[1])[:-2]]

    log("🧠 Decoding article URLs...")
    try:
        articles_params = [
            get_decoding_params(urlparse(article["url"]).path.split("/")[-1])
            for article in df_results.to_dict("records")
            if article.get("url")
        ]
        decoded_urls = decode_urls(articles_params)
    except Exception as e:
        log(f"❌ Failed to decode URLs: {e}")
        return

    # Download articles
    log("📰 Downloading article content...")
    article_data = []
    for raw_url in decoded_urls:
        try:
            url = str(raw_url).strip()
            if not url.startswith("http"):
                continue
            art = Article(url)
            art.download()
            art.parse()
            art.nlp()
            article_data.append({
                "title": art.title,
                "pubdate": art.publish_date.strftime("%m/%d/%Y") if art.publish_date else None,
                "date_collected": today,
                "url": url,
                "summary": art.summary,
                "keywords": art.keywords,
                "FullText": art.text,
            })
        except Exception as e:
            log(f"⚠️ Skipped: {raw_url}\nReason: {e}")

    if not article_data:
        log("❌ No valid articles were scraped.")
        return

    log("💾 Saving files...")
    articledf = pd.DataFrame(article_data)

    # Append/dedup or overwrite
    if mode == "append" and xlsx_path.exists():
        try:
            existing_df = pd.read_excel(xlsx_path)
            combined_df = pd.concat([existing_df, articledf], ignore_index=True)
            articledf = combined_df.drop_duplicates(subset=["url"])
            log(f"🔄 Appended to existing file. Total rows after deduplication: {len(articledf)}")
        except Exception as e:
            log(f"⚠️ Failed to append to existing file: {e}")

    articledf.to_csv(csv_path, index=False, encoding="utf-8-sig")
    articledf.to_excel(xlsx_path, index=False)

    log(f"✅ Scraping complete!\nSaved to:\n  - {csv_path}\n  - {xlsx_path}")


def generate_wordcloud(folder: str, topic_key: str, *, log=_log_default) -> Path | None:
    filename_suffix = topic_key.replace(" ", "_")
    xlsx_path = Path(folder) / topic_key / f"News_{filename_suffix}.xlsx"
    if not xlsx_path.exists():
        log(f"⚠️ Can't find XLSX at {xlsx_path}")
        return None

    log("🌀 Generating word cloud...")

    df = pd.read_excel(xlsx_path)
    if "FullText" not in df.columns or df["FullText"].dropna().empty:
        log("⚠️ No article text found to generate word cloud.")
        return None

    text = " ".join(df["FullText"].dropna().astype(str))
    wc = WordCloud(
        width=1600,
        height=800,
        stopwords=STOPWORDS_CUSTOM,
        background_color="white",
        colormap="coolwarm",
    ).generate(text)

    output_path = Path(folder) / topic_key / f"WordCloud_{filename_suffix}.png"
    wc.to_file(output_path)
    log(f"✅ Word cloud saved to:\n  - {output_path}")
    return output_path


def generate_pdf_report_with_summary(save_folder: str, topic_key: str, search_query: str, top_n_keywords: int = 10) -> str:
    folder = Path(save_folder) / topic_key
    filename_suffix = topic_key.replace(" ", "_")

    wordcloud_path = folder / f"WordCloud_{filename_suffix}.png"
    csv_path = folder / f"News_{filename_suffix}.csv"
    xlsx_path = folder / f"News_{filename_suffix}.xlsx"

    pathdate = datetime.today().strftime("%Y-%m-%d")
    pdf_path = folder / f"NewsReport_{filename_suffix}_{pathdate}.pdf"

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"News Coverage Report: {topic_key}", ln=True)

    current_date = datetime.now().strftime("%B %d, %Y")
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Date: {current_date}", ln=True)
    pdf.multi_cell(0, 10, f"Search Query: {search_query}")
    pdf.ln(5)

    if wordcloud_path.exists():
        image = Image.open(wordcloud_path)
        width, height = image.size
        aspect = height / width
        pdf.image(str(wordcloud_path), x=10, y=None, w=180, h=180 * aspect)
        pdf.ln(10)
    else:
        pdf.set_font("Arial", "I", 12)
        pdf.cell(0, 10, "Word cloud image not found.", ln=True)

    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Topic: {topic_key}", ln=True)
    pdf.cell(0, 10, f"CSV File: {csv_path.name if csv_path.exists() else 'Not found'}", ln=True)
    pdf.cell(0, 10, f"XLSX File: {xlsx_path.name if xlsx_path.exists() else 'Not found'}", ln=True)
    pdf.ln(5)

    if xlsx_path.exists():
        try:
            df = pd.read_excel(xlsx_path)
            num_articles = df.shape[0]
            pdf.cell(0, 10, f"Number of Articles: {num_articles}", ln=True)

            text = " ".join(df.get("FullText", pd.Series(dtype=str)).dropna().astype(str))
            words = re.findall(r"\b\w{4,}\b", text.lower())
            word_freq: dict[str, int] = {}
            for w in words:
                if w not in STOPWORDS_CUSTOM:
                    word_freq[w] = word_freq.get(w, 0) + 1
            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:top_n_keywords]

            pdf.ln(5)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, f"Top {top_n_keywords} Keywords:", ln=True)
            pdf.set_font("Arial", "", 12)
            for word, count in top_words:
                pdf.cell(0, 10, f"{word}: {count}", ln=True)
        except Exception as e:
            pdf.cell(0, 10, f"Error reading data: {str(e)}", ln=True)

    pdf.output(str(pdf_path))
    return str(pdf_path)


# -----------------------------
# GUI
# -----------------------------
HELP_TEXT = (
    "How to Use the News Scraper Tool\n\n"
    "• Choose a folder where your results will be saved.\n"
    "• Select a predefined topic or enter your own custom search.\n"
    "• Click 'Run Scraper' to begin scraping news articles.\n"
    "• Results are saved as .csv and .xlsx in the folder you selected.\n"
    "• Once completed, a word cloud will be displayed and saved.\n"
    "• You can generate a PDF summary report after the scrape completes.\n\n"
    "The scraper pulls articles from Google News from roughly the past 6 months.\n"
    "Publications vary in how they report dates/locations, so query filters may not be perfect.\n\n"
    "Why do some articles appear as 'skipped'?\n"
    "Some pages are paywalled or block scraping. The tool keeps the URL/title but may skip full text.\n\n"
    "Version 1.0 (tkinter port)"
)

# Base64 header image from the original file (kept verbatim)
CERE_B64 = """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"""


@dataclass
class UiState:
    folder: str = ""
    mode: str = "new"  # "new" or "append"
    topic: str = "All Poverty Topics"
    custom_query: str = ""


class NewsScraperApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("News Scraper")
        self.geometry("1150x800")
        self.minsize(1050, 700)

        # NLTK tokenizer used by newspaper3k; best-effort download.
        try:
            nltk.download("punkt", quiet=True)
        except Exception:
            pass

        self.log_sink = LogSink()

        # Variables
        self.var_folder = tk.StringVar(value="")
        self.var_mode = tk.StringVar(value="new")
        self.var_topic = tk.StringVar(value="All Poverty Topics")
        self.var_custom = tk.StringVar(value="")

        self._wordcloud_photo: ImageTk.PhotoImage | None = None
        self._last_search_query_used: str | None = None
        self._last_topic_key_used: str | None = None

        self._build_ui()
        self._wire_events()

        # start polling log queue
        self.after(100, self._drain_log_queue)

    def _build_ui(self) -> None:
        # Top header
        header = ttk.Frame(self, padding=(12, 10))
        header.pack(fill="x")

        try:
            img_bytes = base64.b64decode(CERE_B64)
            pil = Image.open(io.BytesIO(img_bytes))
            self._header_photo = ImageTk.PhotoImage(pil)
            ttk.Label(header, image=self._header_photo).pack(side="left")
        except Exception:
            ttk.Label(header, text="").pack(side="left")

        ttk.Label(
            header,
            text="News Scrape Utility",
            font=("Montserrat", 24),
            padding=(12, 0),
        ).pack(side="left", anchor="w")

        # Main layout: left content + separator + right controls
        main = ttk.Frame(self, padding=(10, 6))
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)

        ttk.Separator(main, orient="vertical").pack(side="left", fill="y", padx=6)

        right = ttk.Frame(main, width=300)
        right.pack(side="left", fill="y")

        # Left: Search parameters frame
        frm_params = ttk.LabelFrame(left, text="Search Parameters", padding=10)
        frm_params.pack(fill="x", padx=4, pady=(0, 8))

        row0 = ttk.Frame(frm_params)
        row0.pack(fill="x", pady=2)
        ttk.Label(row0, text="Save folder:", width=20, font=("Montserrat", 12)).pack(side="left")
        ttk.Entry(row0, textvariable=self.var_folder, width=45, font=("Montserrat", 12)).pack(side="left", padx=(0, 8))
        ttk.Button(row0, text="Browse…", command=self._browse_folder).pack(side="left")

        row1 = ttk.Frame(frm_params)
        row1.pack(fill="x", pady=2)
        tk.Radiobutton(row1, text="Start new scrape", variable=self.var_mode, value="new").pack(side="left", padx=(0, 18))
        tk.Radiobutton(row1, text="Append to existing and deduplicate", variable=self.var_mode, value="append").pack(side="left")

        row2 = ttk.Frame(frm_params)
        row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="Select topic:", width=20, font=("Montserrat", 12)).pack(side="left")
        # Use a plain OptionMenu for maximum cross-platform stability (some ttk Combobox builds crash on open on certain Tk builds).
        self.opt_topic = tk.OptionMenu(row2, self.var_topic, *list(SEARCH_PRESETS.keys()))
        self.opt_topic.configure(width=38)
        self.opt_topic.pack(side="left")

        # Custom query (shown only when Custom Search)
        self.frm_custom = ttk.Frame(frm_params)
        self.frm_custom.pack(fill="x", pady=6)
        self.lbl_custom = ttk.Label(self.frm_custom, text="Custom search term:", width=20, font=("Montserrat", 12))
        self.ent_custom = ttk.Entry(self.frm_custom, textvariable=self.var_custom, width=65, font=("Montserrat", 12))

        # Search term display (shown only when not Custom Search)
        self.frm_query = ttk.Frame(frm_params)
        self.frm_query.pack(fill="x", pady=6)
        self.lbl_query = ttk.Label(self.frm_query, text="Search query:", width=20, font=("Montserrat", 12))
        self.txt_query = tk.Text(self.frm_query, height=2, width=88, wrap="word", font=("Courier", 10))
        self.txt_query.configure(state="disabled", bg="#ffffff")

        # Left: output area + summary + table + image
        frm_out = ttk.LabelFrame(left, text="Scraper Output", padding=10)
        frm_out.pack(fill="both", expand=True, padx=4, pady=(0, 0))

        ttk.Label(frm_out, text="").pack(anchor="w")

        self.txt_output = tk.Text(frm_out, height=7, wrap="word", font=("Courier", 10))
        self.txt_output.pack(fill="x", padx=2, pady=(0, 6))
        self.txt_output.configure(state="disabled", bg="#ffffff")

        self.lbl_summary = ttk.Label(frm_out, text="", font=("Montserrat", 12))
        self.lbl_summary.pack(anchor="w", pady=(2, 6))

        ttk.Label(frm_out, text="Top Keywords Table:", font=("Montserrat", 12)).pack(anchor="w")

        self.tbl = ttk.Treeview(frm_out, columns=("Keyword", "Count"), show="headings", height=10)
        self.tbl.heading("Keyword", text="Keyword")
        self.tbl.heading("Count", text="Count")
        self.tbl.column("Keyword", width=380, anchor="w")
        self.tbl.column("Count", width=120, anchor="w")
        self.tbl.pack(fill="x", pady=(0, 10))

        ttk.Label(frm_out, text="Word Cloud:", font=("Montserrat", 12)).pack(anchor="w")
        self.lbl_wc = ttk.Label(frm_out)
        self.lbl_wc.pack(fill="both", expand=True)

        # Right controls
        self.btn_run = ttk.Button(right, text="Run Scraper", command=self._on_run_scraper)
        self.btn_run.pack(fill="x", pady=(6, 6))

        self.btn_pdf = ttk.Button(right, text="Generate Report", command=self._on_generate_report, state="disabled")
        self.btn_pdf.pack(fill="x", pady=(0, 10))

        ttk.Button(right, text="Clear All", command=self._on_clear).pack(fill="x", pady=(0, 6))
        ttk.Button(right, text="Help", command=self._on_help).pack(fill="x", pady=(0, 6))
        ttk.Button(right, text="Exit", command=self.destroy).pack(fill="x", pady=(0, 10))

        info = (
            "Use this tool to compile a sample of news articles related to your search term(s). "
            "Articles will be downloaded as a spreadsheet into your selected folder and will include "
            "titles, URLs, and keywords. Most articles will also include publication dates and a copy "
            "of the full text.\n\n"
            "After the program has run, a word cloud and summary statistics are displayed. "
            "Optionally, you can download a PDF summary report using the button above."
        )
        ttk.Label(right, text=info, wraplength=270, justify="left", font=("Montserrat", 10)).pack(fill="x")

        self._refresh_topic_visibility()

    def _wire_events(self) -> None:
        self.var_topic.trace_add("write", lambda *_: self._refresh_topic_visibility())

    def _browse_folder(self) -> None:
        path = filedialog.askdirectory(title="Choose a folder to save scraped data")
        if path:
            self.var_folder.set(path)

    def _refresh_topic_visibility(self) -> None:
        topic = self.var_topic.get()
        is_custom = (topic == "Custom Search")

        # custom row
        for w in (self.lbl_custom, self.ent_custom):
            w.pack_forget()
        # query row
        for w in (self.lbl_query, self.txt_query):
            w.pack_forget()

        if is_custom:
            self.lbl_custom.pack(side="left")
            self.ent_custom.pack(side="left", padx=(0, 8))
        else:
            self.lbl_query.pack(side="left")
            self.txt_query.pack(side="left", fill="x", expand=True)
            query = SEARCH_PRESETS.get(topic, "")
            self._set_query_text(query)

    def _set_query_text(self, text: str) -> None:
        self.txt_query.configure(state="normal")
        self.txt_query.delete("1.0", "end")
        self.txt_query.insert("1.0", text)
        self.txt_query.configure(state="disabled")

    def _append_output(self, text: str) -> None:
        self.txt_output.configure(state="normal")
        self.txt_output.insert("end", text)
        self.txt_output.see("end")
        self.txt_output.configure(state="disabled")

    def _drain_log_queue(self) -> None:
        try:
            while True:
                msg = self.log_sink.q.get_nowait()
                self._append_output(msg)
        except queue.Empty:
            pass
        self.after(100, self._drain_log_queue)

    def _reset_keywords_table(self) -> None:
        for item in self.tbl.get_children():
            self.tbl.delete(item)

    def _set_wordcloud_image(self, png_path: Path | None) -> None:
        if not png_path or not png_path.exists():
            self.lbl_wc.configure(image="")
            self._wordcloud_photo = None
            return

        try:
            img = Image.open(png_path)
            img = img.resize((800, 400))
            self._wordcloud_photo = ImageTk.PhotoImage(img)
            self.lbl_wc.configure(image=self._wordcloud_photo)
        except Exception:
            self.lbl_wc.configure(image="")
            self._wordcloud_photo = None

    def _on_clear(self) -> None:
        self.var_folder.set("")
        self.var_mode.set("new")
        self.var_topic.set("All Poverty Topics")
        self.var_custom.set("")

        self.txt_output.configure(state="normal")
        self.txt_output.delete("1.0", "end")
        self.txt_output.configure(state="disabled")

        self.lbl_summary.configure(text="")
        self._reset_keywords_table()
        self._set_wordcloud_image(None)

        self.btn_pdf.configure(state="disabled")
        self._last_search_query_used = None
        self._last_topic_key_used = None

    def _on_help(self) -> None:
        messagebox.showinfo("Help", HELP_TEXT)

    def _validate_inputs(self) -> tuple[str, str, str, str] | None:
        folder = self.var_folder.get().strip()
        if not folder:
            messagebox.showwarning("Missing folder", "Please select a folder first.")
            return None

        topic_key = self.var_topic.get().strip()
        mode = self.var_mode.get().strip()

        if topic_key == "Custom Search":
            searchterm = self.var_custom.get().strip()
            if not searchterm:
                messagebox.showwarning("Missing search term", "Please enter a custom search term.")
                return None
            search_query_for_report = searchterm
        else:
            searchterm = SEARCH_PRESETS.get(topic_key, "").strip()
            if not searchterm:
                messagebox.showwarning("Invalid topic", "Invalid or empty search topic.")
                return None
            search_query_for_report = searchterm

        # Overwrite confirmation if starting new and file exists
        filename_suffix = topic_key.replace(" ", "_")
        xlsx_path = Path(folder) / topic_key / f"News_{filename_suffix}.xlsx"
        if mode == "new" and xlsx_path.exists():
            ok = messagebox.askyesno("Overwrite?", "File already exists. Overwrite?")
            if not ok:
                return None

        return folder, topic_key, searchterm, search_query_for_report

    def _on_run_scraper(self) -> None:
        validated = self._validate_inputs()
        if not validated:
            return

        folder, topic_key, searchterm, search_query_for_report = validated
        mode = self.var_mode.get().strip()

        self.btn_run.configure(state="disabled")
        self.btn_pdf.configure(state="disabled")
        self.lbl_summary.configure(text="")
        self._reset_keywords_table()
        self._set_wordcloud_image(None)

        self._last_search_query_used = search_query_for_report
        self._last_topic_key_used = topic_key

        # clear output
        self.txt_output.configure(state="normal")
        self.txt_output.delete("1.0", "end")
        self.txt_output.configure(state="disabled")

        def worker():
            try:
                run_scraper(folder, searchterm, topic_key, mode, log=self.log_sink.write)
                wc_path = generate_wordcloud(folder, topic_key, log=self.log_sink.write)
                num_articles, top_words = get_article_summary(folder, topic_key)

                def update_ui():
                    if num_articles == 0:
                        self.lbl_summary.configure(text="⚠️ No articles found.\nTry checking your query or running the scraper.")
                        self.btn_pdf.configure(state="disabled")
                    else:
                        self.lbl_summary.configure(text=f"Articles scraped: {num_articles}")
                        self._reset_keywords_table()
                        for word, count in top_words:
                            self.tbl.insert("", "end", values=(word, count))
                        self._set_wordcloud_image(wc_path)
                        self.btn_pdf.configure(state="normal")
                    self.btn_run.configure(state="normal")

                self.after(0, update_ui)

            except Exception:
                err = traceback.format_exc()
                self.log_sink.write("\n❌ Error occurred during scraping:\n" + err + "\n")

                def reenable():
                    self.btn_run.configure(state="normal")
                    self.btn_pdf.configure(state="disabled")

                self.after(0, reenable)

        threading.Thread(target=worker, daemon=True).start()

    def _on_generate_report(self) -> None:
        if not self._last_topic_key_used or not self._last_search_query_used:
            messagebox.showwarning("Nothing to report", "Run the scraper first.")
            return

        folder = self.var_folder.get().strip()
        topic_key = self._last_topic_key_used
        search_query = self._last_search_query_used

        try:
            pdf_path = generate_pdf_report_with_summary(folder, topic_key, search_query)
            messagebox.showinfo("Report Complete", f"✅ PDF report generated successfully.\n\n{pdf_path}")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"❌ Error creating PDF report:\n{e}")


def main() -> None:
    app = NewsScraperApp()
    app.mainloop()


if __name__ == "__main__":
    main()
