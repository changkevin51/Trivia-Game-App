import streamlit as st 
import requests
import pandas as pd
import numpy as np
import json
import random
import html
import time 
from os.path import exists
import base64
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime

Base = declarative_base()
DATABASE_URL = st.secrets["postgresql"]["connection_string"]
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Leaderboard(Base):
    __tablename__ = "leaderboard"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    score = Column(Integer)
    timestamp = Column(String)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

st.set_page_config(
    page_title="Trivia Game",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded",
)

def autoplay_audio(file_path: str):
    with open(file_path, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        md = f"""
            <audio autoplay loop>
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
        st.markdown(
            md,
            unsafe_allow_html=True,
        )

if 'score' not in st.session_state:
    st.session_state.score = 0
if 'total_questions' not in st.session_state:
    st.session_state.total_questions = 0
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame()
if 'current_question' not in st.session_state:
    st.session_state.current_question = None
if 'used_questions' not in st.session_state:
    st.session_state.used_questions = set()
if 'selected_categories' not in st.session_state:
    st.session_state.selected_categories = []
if 'selected_difficulties' not in st.session_state:
    st.session_state.selected_difficulties = []
if 'show_feedback' not in st.session_state:
    st.session_state.show_feedback = False
if 'last_answer_correct' not in st.session_state:
    st.session_state.last_answer_correct = False
if st.session_state.df.empty:
    df = pd.read_csv("questionsList.csv")
    if 'options' not in df.columns:
        df['options'] = df[['option1', 'option2', 'option3', 'option4']].values.tolist()
        df['options'] = df['options'].apply(lambda x: [opt for opt in x if pd.notnull(opt)])
    st.session_state.df = df
else:
    df = st.session_state.df
if 'leaderboard_submitted' not in st.session_state:
    st.session_state.leaderboard_submitted = False

def request_total_question():
    url_total_questions = "https://opentdb.com/api_count_global.php"
    response_total_questions = requests.get(url_total_questions)
    result_total_questions = response_total_questions.json()
    total_number_of_questions = result_total_questions['overall']['total_num_of_verified_questions']
    return total_number_of_questions

def request_token():
    response_token = requests.get("https://opentdb.com/api_token.php?command=request")
    result_token = response_token.json()
    token = result_token['token']
    return token, result_token

def load_data(token):
    url_with_token = 'https://opentdb.com/api.php?amount=50&token='+ token
    response_url= requests.get(url_with_token)
    result = response_url.json()
    json_object = json.dumps(result, indent=4)
    json_object = html.unescape(json_object)
    result = json.loads(json_object)
    list_values = []
    for item in result['results']:
        list_values.append(item)
    df = pd.DataFrame(data = list_values)
    return df

def load_new_data(df, token):
    url_with_token = 'https://opentdb.com/api.php?amount=50&token='+ token
    response_url= requests.get(url_with_token)
    result = response_url.json()
    json_object = json.dumps(result, indent=4)
    json_object = html.unescape(json_object)
    result = json.loads(json_object)
    list_values = []
    for item in result['results']:
        list_values.append(item)
    df_new = pd.DataFrame(data = list_values)
    frames = [df, df_new]
    df = pd.concat(frames, ignore_index=True)
    return df

def load_data_single_amount(df, token):
    url_with_token = 'https://opentdb.com/api.php?amount=1&token='+ token
    response_url= requests.get(url_with_token)
    result = response_url.json()
    json_object = json.dumps(result, indent=4)
    json_object = html.unescape(json_object)
    result = json.loads(json_object)
    list_values = []
    for item in result['results']:
        list_values.append(item)
    df_per_single = pd.DataFrame(data = list_values)
    frames = [df, df_per_single]
    df = pd.concat(frames, ignore_index=True)
    return df

def fetch_and_prepare_questions():
    total_number_of_questions = request_total_question()
    token, result_token = request_token()
    df = load_data(token)
    count_calls = divmod(total_number_of_questions, 50)
    for i in range(0, count_calls[0] - 1):
        time.sleep(5)
        df = load_new_data(df, token)
    for i in range(len(df), total_number_of_questions):
        time.sleep(5)
        df = load_data_single_amount(df, token)
    df = transform_data(df)
    return df

def select_category_and_difficulty(df):
    st.write("# Trivia Game")

    categories = df['category'].unique()
    difficulties = df['difficulty'].unique()

    st.write("## Choose Categories:")
    
    if 'all_selected' not in st.session_state:
        st.session_state.all_selected = False

    if st.button("Select/Deselect All Categories"):
        st.session_state.all_selected = not st.session_state.all_selected

    if st.session_state.all_selected:
        selected_categories = categories.tolist()
    else:
        selected_categories = []

    selected_categories = st.pills("Select one or more categories", options=categories.tolist(), selection_mode="multi", default=selected_categories)
    st.session_state.selected_categories = selected_categories

    st.write("## Choose Difficulties:")
    selected_difficulties = st.multiselect("Select one or more difficulties", options=difficulties.tolist(), default=difficulties.tolist())
    st.session_state.selected_difficulties = selected_difficulties

def display_sidebar(df):
    total_questions = st.session_state.total_questions
    score = st.session_state.score
    if total_questions > 0:
        score_percent = (score / total_questions) * 100
    else:
        score_percent = 0
    rainbow_text = f':rainbow[Score: {score}/{total_questions} ({score_percent:.0f}%)]'
    st.sidebar.header(rainbow_text)
    st.sidebar.header("")
    st.sidebar.write("Total Questions:", len(df['question']))
    st.sidebar.write("Total Categories:", len(df['category'].unique()))
    st.sidebar.write("Total Difficulty Levels:", len(df['difficulty'].unique()))
    st.sidebar.write("Total Types:", len(df['type'].unique()))
    st.sidebar.write("Total Questions per Difficulty level:")
    st.sidebar.write(df['difficulty'].value_counts())
    st.sidebar.write("Total Questions per Type:")
    st.sidebar.write(df['type'].value_counts())
    st.sidebar.header("")
    on = st.sidebar.toggle("Music")
    if on:
        autoplay_audio("music.mp3")
    
    st.sidebar.header("")
    st.sidebar.caption("This app uses the OpenTrivia Library.")
    st.sidebar.caption("A project by Kevin Chang")
        
def transform_data(df):
    df['option1'] = df['correct_answer'].copy()
    df[['option2', 'option3', 'option4']] = df["incorrect_answers"].apply(pd.Series)
    df = df.drop(['incorrect_answers'], axis=1)
    df['options'] = df[['option1', 'option2', 'option3', 'option4']].values.tolist()
    df['options'] = df['options'].apply(lambda x: [opt for opt in x if pd.notnull(opt)])
    df['options'] = df['options'].apply(random.sample, k=len)
    df.to_csv('questionsList.csv', index=False)
    return df

def get_random_question(df):
    filtered_df = df[df['category'].isin(st.session_state.selected_categories) & df['difficulty'].isin(st.session_state.selected_difficulties)]
    filtered_df = filtered_df[~filtered_df.index.isin(st.session_state.used_questions)]
    if filtered_df.empty:
        st.write("Please select at least one category and difficulty.")
        return None
    question = filtered_df.sample(n=1)
    st.session_state.current_question = question.iloc[0]
    st.session_state.used_questions.add(question.index[0])
    return st.session_state.current_question

def display_question(question):
    st.write(f"### Q: {question['question']}")
    options = question['options']
    selected_answer = st.radio("Choose your answer:", options)
    return selected_answer

def check_answer(selected_answer, question):
    correct_answer = question['correct_answer']
    st.session_state.total_questions += 1
    if selected_answer == correct_answer:
        st.session_state.score += 1
        st.session_state.last_answer_correct = True
        st.success(f"Correct! You have {st.session_state.score} out of {st.session_state.total_questions} points.")
    else:
        st.session_state.last_answer_correct = False
        st.warning(f"Incorrect. The correct answer was: {correct_answer}. You have {st.session_state.score} out of {st.session_state.total_questions} points.")

def save_score(username, score):
    from sqlalchemy.orm import Session
    db = Session(bind=engine)
    new_entry = Leaderboard(username=username, score=score, timestamp=str(datetime.now()))
    db.add(new_entry)
    db.commit()
    db.close()
    st.success(f"Score saved for {username}!")

def show_leaderboard():
    db = Session(bind=engine)
    results = db.query(Leaderboard).order_by(Leaderboard.score.desc()).limit(10).all()
    db.close()
    
    st.header("🏆 Global Leaderboard")
    if results:
        leaderboard_df = pd.DataFrame([{"Name": r.username, "Score": r.score, "Time": pd.to_datetime(r.timestamp).strftime('%Y-%m-%d %H:%M:%S')} for r in results])
        st.table(leaderboard_df)
    else:
        st.write("No scores yet! Be the first to play.")

def main():
    if not exists('questionsList.csv'):
        st.info("#### Please press the button to load the questions!")
        if st.sidebar.button('Fetch Questions', key='fetch_questions_button'):
            with st.spinner('Loading the questions... This may take several minutes!'):
                df = fetch_and_prepare_questions()
                st.session_state.df = df
                st.success("Questions loaded successfully!")
                st.experimental_rerun()
    else:
        if st.session_state.df.empty:
            df = pd.read_csv("questionsList.csv")
            df['options'] = df['options'].apply(eval)
            st.session_state.df = df
        else:
            df = st.session_state.df

        display_sidebar(df)
        select_category_and_difficulty(df)

        if 'current_question' not in st.session_state:
            st.session_state.current_question = None
        if 'answer_submitted' not in st.session_state:
            st.session_state.answer_submitted = False
        if 'leaderboard_submitted' not in st.session_state:
            st.session_state.leaderboard_submitted = False

        if st.button('Next Question', key='next_question_button'):
            st.session_state.current_question = None
            st.session_state.answer_submitted = False

        if st.session_state.current_question is None:
            question = get_random_question(df)
            if question is not None:
                st.session_state.current_question = question
            else:
                st.write("No more questions available. You can adjust your filters or restart the game.")
                return

        if st.session_state.current_question is not None:
            question = st.session_state.current_question

            if not st.session_state.answer_submitted:
                with st.form("Answer Form"):
                    selected_answer = display_question(question)
                    submit_button = st.form_submit_button("Submit")
                    if submit_button:
                        check_answer(selected_answer, question)
                        st.session_state.answer_submitted = True
            else:
                st.write("Click 'Next Question' to proceed.")

        if st.session_state.total_questions > 0:
            if not st.session_state.leaderboard_submitted:
                st.write("### Enter your name to save your score on the leaderboard")
                st.warning("⚠️ Once you submit, you cannot change your score or name.")
                
                with st.form("Leaderboard Form"):
                    username = st.text_input("Enter your name:")
                    submit_button = st.form_submit_button("Submit Score")

                    if submit_button:
                        if username.strip():
                            save_score(username, st.session_state.score)
                            st.session_state.leaderboard_submitted = True
                        else:
                            st.warning("Please enter a valid name.")
            else:
                st.info("Your score has been submitted. Thank you for playing!")

if __name__ == '__main__':
    main()
