"""
Data Preprocessing Script
Prepares the ticket dataset for ML model training
- Filters English tickets
- Combines subject and body
- Generates sentiment labels
- Splits into train/val/test sets
"""

import pandas as pd
import numpy as np
from pathlib import Path
from textblob import TextBlob
from sklearn.model_selection import train_test_split

def calculate_sentiment(text):
    """Calculate sentiment using TextBlob and categorize"""
    try:
        if pd.isna(text) or str(text).strip() == "":
            return "Neutral"
        
        blob = TextBlob(str(text))
        polarity = blob.sentiment.polarity
        
        # Categorize based on polarity
        if polarity < -0.3:
            return "Urgent"
        elif polarity < 0:
            return "Negative"
        elif polarity == 0:
            return "Neutral"
        else:
            return "Positive"
    except:
        return "Neutral"

def preprocess_data(sample_size=None, language_filter='en'):
    """
    Preprocess the ticket dataset
    
    Args:
        sample_size: Number of tickets to sample (None = use all available)
        language_filter: Language to filter ('en' for English, None for all)
    """
    
    print("\n" + "="*80)
    print("TICKET DATA PREPROCESSING")
    print("="*80)
    
    # Load data
    data_path = Path(__file__).parent.parent / "Data" / "aa_dataset-tickets-multi-lang-5-2-50-version.csv"
    print(f"\nLoading data from: {data_path}")
    
    df = pd.read_csv(data_path)
    print(f"Original dataset size: {len(df):,} tickets")
    
    # Filter by language if specified
    if language_filter:
        df = df[df['language'] == language_filter].copy()
        print(f"After filtering for '{language_filter}': {len(df):,} tickets")
    
    # Sample data for faster training
    if sample_size and len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42).reset_index(drop=True)
        print(f"Sampled to: {len(df):,} tickets")
    
    print("\n" + "-"*80)
    print("FEATURE ENGINEERING")
    print("-"*80)
    
    # Combine subject and body into ticket_text
    df['ticket_text'] = df['subject'].fillna('') + ' ' + df['body'].fillna('')
    df['ticket_text'] = df['ticket_text'].str.strip()
    print("✓ Created 'ticket_text' from subject + body")
    
    # Map dataset columns to our ML fields
    df['category'] = df['type']  # Incident, Request, Problem
    df['priority'] = df['priority']  # low, medium, high
    df['department'] = df['queue']  # Department/Queue
    
    # Generate sentiment labels
    print("\nGenerating sentiment labels...")
    df['sentiment'] = df['ticket_text'].apply(calculate_sentiment)
    print("✓ Generated 'sentiment' labels")
    
    # Keep the answer for LLM context
    df['answer'] = df['answer'].fillna('')
    
    # Select relevant columns
    columns_to_keep = [
        'ticket_text',
        'category',
        'priority', 
        'department',
        'sentiment',
        'answer'
    ]
    
    df_processed = df[columns_to_keep].copy()
    
    # Remove any rows with missing critical values
    print("\nCleaning data...")
    before_clean = len(df_processed)
    df_processed = df_processed.dropna(subset=['ticket_text', 'category', 'priority', 'department'])
    df_processed = df_processed[df_processed['ticket_text'].str.len() > 10]  # Remove very short tickets
    after_clean = len(df_processed)
    print(f"✓ Removed {before_clean - after_clean} incomplete records")
    print(f"Final dataset size: {after_clean:,} tickets")
    
    print("\n" + "-"*80)
    print("LABEL DISTRIBUTIONS")
    print("-"*80)
    
    print("\nCategory:")
    print(df_processed['category'].value_counts())
    
    print("\nPriority:")
    print(df_processed['priority'].value_counts())
    
    print("\nDepartment:")
    print(df_processed['department'].value_counts())
    
    print("\nSentiment:")
    print(df_processed['sentiment'].value_counts())
    
    print("\n" + "-"*80)
    print("TRAIN/VAL/TEST SPLIT")
    print("-"*80)
    
    # Split: 70% train, 15% val, 15% test
    train_df, temp_df = train_test_split(
        df_processed, 
        test_size=0.3, 
        random_state=42,
        stratify=df_processed['category']
    )
    
    val_df, test_df = train_test_split(
        temp_df,
        test_size=0.5,
        random_state=42,
        stratify=temp_df['category']
    )
    
    print(f"Train set: {len(train_df):,} tickets ({len(train_df)/len(df_processed)*100:.1f}%)")
    print(f"Validation set: {len(val_df):,} tickets ({len(val_df)/len(df_processed)*100:.1f}%)")
    print(f"Test set: {len(test_df):,} tickets ({len(test_df)/len(df_processed)*100:.1f}%)")
    
    # Save processed datasets
    output_dir = Path(__file__).parent.parent / "Data"
    
    train_path = output_dir / "train_data.csv"
    val_path = output_dir / "val_data.csv"
    test_path = output_dir / "test_data.csv"
    
    train_df.to_csv(train_path, index=False)
    val_df.to_csv(val_path, index=False)
    test_df.to_csv(test_path, index=False)
    
    print("\n" + "-"*80)
    print("SAVED FILES")
    print("-"*80)
    print(f"✓ {train_path}")
    print(f"✓ {val_path}")
    print(f"✓ {test_path}")
    
    print("\n" + "="*80)
    print("PREPROCESSING COMPLETE!")
    print("="*80)
    
    return train_df, val_df, test_df

if __name__ == "__main__":
    # Use all English tickets (16,338) for maximum accuracy
    train_df, val_df, test_df = preprocess_data(sample_size=None, language_filter='en')
    
    # Show sample
    print("\nSample processed ticket:")
    print("-"*80)
    sample = train_df.iloc[0]
    print(f"Ticket Text: {sample['ticket_text'][:200]}...")
    print(f"Category: {sample['category']}")
    print(f"Priority: {sample['priority']}")
    print(f"Department: {sample['department']}")
    print(f"Sentiment: {sample['sentiment']}")
