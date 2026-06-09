"""
ML Predictor Module - HYBRID APPROACH
Loads trained models and makes predictions on new tickets with confidence scoring.

Features:
- Uses Sentence Transformers for semantic embeddings
- XGBoost classifiers for multi-class prediction
- Confidence scores for LLM fallback routing
- Label encoders for proper categorical handling
"""

import joblib
from pathlib import Path
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer

class TicketMLPredictor:
    """ML predictor for ticket classification with confidence-based LLM fallback"""
    
    def __init__(self, models_dir=None, confidence_threshold=0.65):
        """
        Initialize the ML predictor
        
        Args:
            models_dir: Path to directory containing trained models
            confidence_threshold: Minimum confidence to trust ML prediction (default 0.65)
        """
        if models_dir is None:
            models_dir = Path(__file__).parent / "models"
        else:
            models_dir = Path(models_dir)
        
        self.models_dir = models_dir
        self.confidence_threshold = confidence_threshold
        self.embedding_model = None
        self.models = {}
        self.label_encoders = {}
        self._load_models()
    
    def _load_models(self):
        """Load all trained models, embedding model, and label encoders"""
        
        # Load Sentence Transformer
        embedding_model_path = self.models_dir / "sentence_transformer_model"
        if not embedding_model_path.exists():
            raise FileNotFoundError(
                f"Sentence Transformer model not found at {embedding_model_path}. "
                "Please run 03_train_ml_model.py first."
            )
        
        print("Loading Sentence Transformer model...")
        self.embedding_model = SentenceTransformer(str(embedding_model_path))
        print("✓ Sentence Transformer loaded")
        
        # Load classification models and label encoders
        model_names = ['category', 'priority', 'department', 'sentiment']
        
        for model_name in model_names:
            model_path = self.models_dir / f"{model_name}_model.pkl"
            encoder_path = self.models_dir / f"{model_name}_label_encoder.pkl"
            
            if not model_path.exists():
                raise FileNotFoundError(
                    f"Model not found at {model_path}. "
                    "Please run 03_train_ml_model.py first."
                )
            
            if not encoder_path.exists():
                raise FileNotFoundError(
                    f"Label encoder not found at {encoder_path}. "
                    "Please run 03_train_ml_model.py first."
                )
            
            self.models[model_name] = joblib.load(model_path)
            self.label_encoders[model_name] = joblib.load(encoder_path)
        
        print(f"✓ Loaded {len(self.models)} XGBoost classifiers")
        print(f"✓ Loaded {len(self.label_encoders)} label encoders")
    
    def predict(self, ticket_text):
        """
        Predict all labels for a single ticket
        
        Args:
            ticket_text: The ticket text (subject + body)
        
        Returns:
            Dictionary with predictions for all labels
        """
        
        # Create embedding
        embedding = self.embedding_model.encode([ticket_text], convert_to_numpy=True)
        
        # Make predictions
        predictions = {}
        
        for model_name, model in self.models.items():
            # Get probability distribution
            proba = model.predict_proba(embedding)[0]
            
            # Get predicted class index
            pred_idx = proba.argmax()
            
            # Decode to original label
            pred_label = self.label_encoders[model_name].inverse_transform([pred_idx])[0]
            
            # Get confidence
            confidence = float(proba[pred_idx])
            
            # Create probability dictionary with original labels
            classes = self.label_encoders[model_name].classes_
            probabilities = {
                cls: float(prob) 
                for cls, prob in zip(classes, proba)
            }
            
            predictions[model_name] = {
                'prediction': pred_label,
                'confidence': confidence,
                'probabilities': probabilities
            }
        
        return predictions
    
    def predict_with_fallback_check(self, ticket_text):
        """
        Predict with confidence checking for LLM fallback routing
        
        Args:
            ticket_text: The ticket text (subject + body)
        
        Returns:
            Tuple of (predictions_dict, needs_llm_fallback)
        """
        
        predictions = self.predict(ticket_text)
        
        # Check if any prediction has low confidence
        low_confidence_fields = []
        
        for field_name, result in predictions.items():
            if result['confidence'] < self.confidence_threshold:
                low_confidence_fields.append(field_name)
        
        needs_llm = len(low_confidence_fields) > 0
        
        return predictions, needs_llm, low_confidence_fields
    
    def predict_batch(self, ticket_texts):
        """
        Predict labels for multiple tickets
        
        Args:
            ticket_texts: List of ticket texts
        
        Returns:
            List of prediction dictionaries
        """
        
        # Create embeddings for all texts
        embeddings = self.embedding_model.encode(ticket_texts, convert_to_numpy=True)
        
        # Make predictions
        batch_predictions = []
        
        for i in range(len(ticket_texts)):
            embedding = embeddings[i:i+1]
            predictions = {}
            
            for model_name, model in self.models.items():
                proba = model.predict_proba(embedding)[0]
                pred_idx = proba.argmax()
                pred_label = self.label_encoders[model_name].inverse_transform([pred_idx])[0]
                confidence = float(proba[pred_idx])
                
                classes = self.label_encoders[model_name].classes_
                probabilities = {
                    cls: float(prob)
                    for cls, prob in zip(classes, proba)
                }
                
                predictions[model_name] = {
                    'prediction': pred_label,
                    'confidence': confidence,
                    'probabilities': probabilities
                }
            
            batch_predictions.append(predictions)
        
        return batch_predictions
    
    def get_model_info(self):
        """Get information about loaded models"""
        
        info = {
            'embedding_model': {
                'name': 'all-MiniLM-L6-v2',
                'embedding_dimension': self.embedding_model.get_sentence_embedding_dimension(),
                'type': 'Sentence Transformer'
            },
            'classifier': {
                'type': 'XGBoost',
                'confidence_threshold': self.confidence_threshold
            },
            'models': {}
        }
        
        for model_name in self.models.keys():
            classes = self.label_encoders[model_name].classes_
            info['models'][model_name] = {
                'classes': list(classes),
                'n_classes': len(classes)
            }
        
        return info

# Example usage
if __name__ == "__main__":
    
    # Initialize predictor
    print("Initializing ML Predictor with Hybrid Approach...")
    predictor = TicketMLPredictor(confidence_threshold=0.65)
    
    # Example ticket
    example_ticket = """
    Unable to connect VPN since morning, urgent client call in 20 mins.
    I've tried restarting my laptop and the VPN client but still getting connection timeout errors.
    This is blocking critical work. Please help ASAP!
    """
    
    print("="*80)
    print("ML PREDICTOR TEST - HYBRID APPROACH")
    print("="*80)
    
    print(f"\nTicket Text:\n{example_ticket.strip()}\n")
    
    # Make prediction with fallback check
    predictions, needs_llm, low_confidence_fields = predictor.predict_with_fallback_check(example_ticket)
    
    print("="*80)
    print("PREDICTIONS")
    print("="*80)
    
    for label, result in predictions.items():
        confidence_flag = "⚠️ LOW" if result['confidence'] < predictor.confidence_threshold else "✓ HIGH"
        print(f"\n{label.upper()}: {confidence_flag}")
        print(f"  Prediction: {result['prediction']}")
        print(f"  Confidence: {result['confidence']*100:.2f}%")
        print(f"  Top 3 Probabilities:")
        sorted_probs = sorted(result['probabilities'].items(), key=lambda x: x[1], reverse=True)[:3]
        for cls, prob in sorted_probs:
            print(f"    {cls}: {prob*100:.2f}%")
    
    print("\n" + "="*80)
    print("LLM FALLBACK ROUTING")
    print("="*80)
    
    if needs_llm:
        print(f"⚠️  LLM fallback NEEDED for: {', '.join(low_confidence_fields)}")
        print(f"   Reason: Confidence below threshold ({predictor.confidence_threshold*100:.0f}%)")
    else:
        print("✓ ML predictions are confident. No LLM fallback needed.")
    
    # Model info
    print("\n" + "="*80)
    print("MODEL INFO")
    print("="*80)
    
    info = predictor.get_model_info()
    print(f"\nEmbedding Model: {info['embedding_model']['name']}")
    print(f"Embedding Dimension: {info['embedding_model']['embedding_dimension']}")
    print(f"Classifier: {info['classifier']['type']}")
    print(f"Confidence Threshold: {info['classifier']['confidence_threshold']*100:.0f}%")
    print(f"\nModel classes:")
    for model_name, model_info in info['models'].items():
        print(f"  {model_name}: {model_info['classes']}")
