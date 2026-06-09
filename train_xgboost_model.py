"""
ML Model Training Script - HYBRID APPROACH
Trains classification models using:
- Sentence Transformers (all-MiniLM-L6-v2) for semantic embeddings
- XGBoost for powerful classification
- Label encoding for proper handling of categorical targets

Models trained for:
1. Category (Incident Type)
2. Priority 
3. Department (Route to)
4. Sentiment
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
import xgboost as xgb
import joblib
import matplotlib.pyplot as plt
import seaborn as sns

def train_classifier(X_train, y_train, X_val, y_val, label_name, label_encoder):
    """Train an XGBoost classifier with semantic embeddings"""
    
    print(f"\n{'='*80}")
    print(f"TRAINING {label_name.upper()} CLASSIFIER")
    print('='*80)
    
    # Encode labels
    y_train_encoded = label_encoder.fit_transform(y_train)
    y_val_encoded = label_encoder.transform(y_val)
    
    print(f"Classes: {list(label_encoder.classes_)}")
    print(f"Number of classes: {len(label_encoder.classes_)}")
    
    # Calculate class weights for imbalanced data
    class_counts = np.bincount(y_train_encoded)
    total_samples = len(y_train_encoded)
    n_classes = len(label_encoder.classes_)
    
    # Create sample weights
    sample_weights = np.zeros(len(y_train_encoded))
    for i, class_idx in enumerate(y_train_encoded):
        sample_weights[i] = total_samples / (n_classes * class_counts[class_idx])
    
    # Train XGBoost model
    print("Training XGBoost model...")
    model = xgb.XGBClassifier(
        max_depth=6,
        learning_rate=0.1,
        n_estimators=200,
        objective='multi:softprob',
        eval_metric='mlogloss',
        use_label_encoder=False,
        random_state=42,
        tree_method='hist',
        enable_categorical=False
    )
    
    model.fit(
        X_train, 
        y_train_encoded,
        sample_weight=sample_weights,
        eval_set=[(X_val, y_val_encoded)],
        verbose=False
    )
    print("[OK] Model trained")
    
    # Evaluate on training set
    train_pred = model.predict(X_train)
    train_pred_labels = label_encoder.inverse_transform(train_pred)
    train_acc = accuracy_score(y_train, train_pred_labels)
    print(f"\nTraining Accuracy: {train_acc*100:.2f}%")
    
    # Evaluate on validation set
    val_pred = model.predict(X_val)
    val_pred_labels = label_encoder.inverse_transform(val_pred)
    val_acc = accuracy_score(y_val, val_pred_labels)
    print(f"Validation Accuracy: {val_acc*100:.2f}%")
    
    # Detailed classification report
    print(f"\nValidation Classification Report:")
    print("-"*80)
    print(classification_report(y_val, val_pred_labels))
    
    # Confusion matrix
    cm = confusion_matrix(y_val, val_pred_labels, labels=label_encoder.classes_)
    
    return model, label_encoder, val_acc, cm

def plot_confusion_matrices(cms, labels, output_path):
    """Plot confusion matrices for all classifiers"""
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    axes = axes.flatten()
    
    for idx, (cm, label_name) in enumerate(zip(cms, labels)):
        sns.heatmap(
            cm, 
            annot=True, 
            fmt='d', 
            cmap='Blues', 
            ax=axes[idx],
            cbar_kws={'label': 'Count'}
        )
        axes[idx].set_title(f'{label_name} Confusion Matrix', fontsize=14, fontweight='bold')
        axes[idx].set_ylabel('True Label')
        axes[idx].set_xlabel('Predicted Label')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n[OK] Confusion matrices saved to: {output_path}")

def train_all_models():
    """Train all classification models using Sentence Transformers + XGBoost"""
    
    print("\n" + "="*80)
    print("ML MODEL TRAINING PIPELINE - HYBRID APPROACH")
    print("Sentence Transformers + XGBoost + Label Encoding")
    print("="*80)
    
    # Load preprocessed data
    data_dir = Path(__file__).parent / "Data"
    
    print("\nLoading preprocessed data...")
    train_df = pd.read_csv(data_dir / "train_data.csv")
    val_df = pd.read_csv(data_dir / "val_data.csv")
    test_df = pd.read_csv(data_dir / "test_data.csv")
    
    print(f"[OK] Train: {len(train_df):,} tickets")
    print(f"[OK] Validation: {len(val_df):,} tickets")
    print(f"[OK] Test: {len(test_df):,} tickets")
    
    # Load Sentence Transformer model
    print("\n" + "="*80)
    print("LOADING SENTENCE TRANSFORMER MODEL")
    print("="*80)
    print("Model: all-MiniLM-L6-v2")
    print("This creates semantic embeddings that understand meaning, not just words.")
    
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    print("[OK] Sentence Transformer loaded")
    
    # Create embeddings
    print("\n" + "="*80)
    print("CREATING SEMANTIC EMBEDDINGS")
    print("="*80)
    
    print("Encoding training data...")
    X_train = embedding_model.encode(
        train_df['ticket_text'].tolist(),
        show_progress_bar=True,
        convert_to_numpy=True
    )
    
    print("Encoding validation data...")
    X_val = embedding_model.encode(
        val_df['ticket_text'].tolist(),
        show_progress_bar=True,
        convert_to_numpy=True
    )
    
    print("Encoding test data...")
    X_test = embedding_model.encode(
        test_df['ticket_text'].tolist(),
        show_progress_bar=True,
        convert_to_numpy=True
    )
    
    print(f"\n[OK] Embeddings created")
    print(f"  Embedding dimension: {X_train.shape[1]}")
    print(f"  Train shape: {X_train.shape}")
    print(f"  Val shape: {X_val.shape}")
    print(f"  Test shape: {X_test.shape}")
    
    # Save embedding model
    models_dir = Path(__file__).parent / "models"
    embedding_model_path = models_dir / "sentence_transformer_model"
    embedding_model.save(str(embedding_model_path))
    print(f"[OK] Sentence Transformer saved to: {embedding_model_path}")
    
    # Train models for each label
    models = {}
    label_encoders = {}
    accuracies = {}
    confusion_matrices = []
    label_names = ['Category', 'Priority', 'Department', 'Sentiment']
    target_columns = ['category', 'priority', 'department', 'sentiment']
    
    for label_name, target_col in zip(label_names, target_columns):
        y_train = train_df[target_col]
        y_val = val_df[target_col]
        
        # Create label encoder
        label_encoder = LabelEncoder()
        
        model, label_encoder, val_acc, cm = train_classifier(
            X_train, y_train, 
            X_val, y_val,
            label_name,
            label_encoder
        )
        
        models[target_col] = model
        label_encoders[target_col] = label_encoder
        accuracies[target_col] = val_acc
        confusion_matrices.append(cm)
        
        # Save model and label encoder
        model_path = models_dir / f"{target_col}_model.pkl"
        joblib.dump(model, model_path)
        print(f"[OK] Model saved to: {model_path}")
        
        encoder_path = models_dir / f"{target_col}_label_encoder.pkl"
        joblib.dump(label_encoder, encoder_path)
        print(f"[OK] Label encoder saved to: {encoder_path}")
    
    # Plot confusion matrices
    cm_output_path = models_dir / "confusion_matrices.png"
    plot_confusion_matrices(confusion_matrices, label_names, cm_output_path)
    
    # Final summary
    print("\n" + "="*80)
    print("TRAINING SUMMARY")
    print("="*80)
    
    print("\nValidation Accuracies:")
    for label_name, target_col in zip(label_names, target_columns):
        print(f"  {label_name:15s}: {accuracies[target_col]*100:6.2f}%")
    
    avg_accuracy = np.mean(list(accuracies.values()))
    print(f"\n  Average Accuracy: {avg_accuracy*100:.2f}%")
    
    # Test set evaluation
    print("\n" + "="*80)
    print("TEST SET EVALUATION")
    print("="*80)
    
    for label_name, target_col in zip(label_names, target_columns):
        y_test = test_df[target_col]
        
        # Encode test labels
        y_test_encoded = label_encoders[target_col].transform(y_test)
        
        # Predict
        test_pred_encoded = models[target_col].predict(X_test)
        test_pred = label_encoders[target_col].inverse_transform(test_pred_encoded)
        
        test_acc = accuracy_score(y_test, test_pred)
        print(f"  {label_name:15s}: {test_acc*100:6.2f}%")
    
    print("\n" + "="*80)
    print("MODEL TRAINING COMPLETE!")
    print("="*80)
    print(f"\nAll models and encoders saved to: {models_dir}")
    print("\nNext: The ml_predictor.py will load these models for inference.")
    print("XGBoost will provide confidence scores for LLM fallback routing.")
    
    return models, label_encoders, embedding_model, accuracies

if __name__ == "__main__":
    models, label_encoders, embedding_model, accuracies = train_all_models()
