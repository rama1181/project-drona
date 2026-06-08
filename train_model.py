import pandas as pd
import numpy as np
import os
import joblib
import sqlite3
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
DB_PATH = os.path.join(os.path.dirname(__file__), "smart_ticket_engine.db")
CSV_PATH = os.path.join(os.path.dirname(__file__), "tickets_dataset.csv")

def train_and_save_models():
    os.makedirs(MODELS_DIR, exist_ok=True)
    
    # Load data from database if available, otherwise fallback to CSV
    if os.path.exists(DB_PATH):
        try:
            print(f"Loading ticket training dataset from SQLite database: {DB_PATH}")
            conn = sqlite3.connect(DB_PATH)
            df = pd.read_sql_query("SELECT ticket_text, incident_type, final_priority, department, sentiment FROM tickets", conn)
            conn.close()
            # If DB is empty, raise exception to trigger fallback
            if len(df) == 0:
                raise ValueError("Database table 'tickets' is empty.")
        except Exception as e:
            print(f"Failed to load from database: {e}. Falling back to CSV.")
            df = pd.read_csv(CSV_PATH)
    else:
        print(f"Loading training dataset from CSV: {CSV_PATH}")
        df = pd.read_csv(CSV_PATH)
        
    print(f"Dataset loaded with {len(df)} samples.")
    
    # Fill empty text just in case
    df['ticket_text'] = df['ticket_text'].fillna('')
    
    # Vectorizer fitting
    print("Fitting RAG and classification TF-IDF Vectorizer...")
    vectorizer = TfidfVectorizer(stop_words='english', min_df=1, max_df=1.0, ngram_range=(1, 2))
    X = vectorizer.fit_transform(df['ticket_text'])
    
    # Save the vectorizer
    vectorizer_path = os.path.join(MODELS_DIR, "rag_vectorizer.pkl")
    joblib.dump(vectorizer, vectorizer_path)
    print(f"Saved TF-IDF Vectorizer to {vectorizer_path}")
    
    targets = {
        "incident_type": ("incident_type_model.pkl", "incident_type"),
        "priority": ("priority_model.pkl", "final_priority"),
        "department": ("department_model.pkl", "department"),
        "sentiment": ("sentiment_model.pkl", "sentiment")
    }
    
    metrics_summary = {}
    
    for key, (filename, col) in targets.items():
        print(f"\n--- Training Model for: {key.upper()} (Target: {col}) ---")
        y = df[col].fillna('Unknown')
        
        # Split data for evaluation
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y if len(y.value_counts()) > 1 else None)
        
        # Train model
        model = LogisticRegression(class_weight='balanced', max_iter=1000, C=1.0)
        model.fit(X_train, y_train)
        
        # Predict & Evaluate
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        
        print(f"Accuracy: {acc:.4f}")
        print("Classification Report:")
        print(classification_report(y_test, y_pred, zero_division=0))
        print("Confusion Matrix:")
        print(confusion_matrix(y_test, y_pred))
        
        # Save trained model on FULL dataset
        full_model = LogisticRegression(class_weight='balanced', max_iter=1000, C=1.0)
        full_model.fit(X, y)
        model_path = os.path.join(MODELS_DIR, filename)
        joblib.dump(full_model, model_path)
        print(f"Saved {key} model to {model_path}")
        
        # Generate classification report details for visualization/re-training log
        report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
        metrics_summary[key] = {
            "accuracy": float(acc),
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
            "classes": list(full_model.classes_),
            "classification_report": report
        }
        
    return metrics_summary

if __name__ == "__main__":
    train_and_save_models()
