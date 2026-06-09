"""
Ticket Processor Module - HYBRID APPROACH
Combines ML classification with LLM fallback for complete ticket analysis

Features:
- ML prediction with confidence scoring
- LLM fallback for low-confidence predictions
- Recommended next action generation
"""

from ml_predictor import TicketMLPredictor
from llm_client import GroqLLMClient
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class TicketProcessor:
    """Complete ticket processing pipeline with hybrid ML+LLM approach"""
    
    def __init__(self, models_dir=None, groq_api_key=None, llm_model="llama-3.3-70b-versatile", confidence_threshold=0.65):
        """
        Initialize ticket processor
        
        Args:
            models_dir: Path to ML models directory
            groq_api_key: Groq API key
            llm_model: LLM model to use
            confidence_threshold: Minimum confidence for ML predictions (default 0.65)
        """
        
        # Initialize ML predictor with confidence threshold
        self.ml_predictor = TicketMLPredictor(
            models_dir=models_dir,
            confidence_threshold=confidence_threshold
        )
        
        # Initialize LLM client
        try:
            self.llm_client = GroqLLMClient(api_key=groq_api_key, model=llm_model)
            self.llm_available = True
        except ValueError as e:
            print(f"⚠️  Warning: {e}")
            print("LLM features will use fallback mode.")
            self.llm_client = None
            self.llm_available = False
    
    def process_ticket(self, ticket_text):
        """
        Process a single ticket through the hybrid pipeline
        
        Pipeline:
        1. Get ML predictions with confidence scores
        2. If any confidence is low, use LLM for classification
        3. Generate recommended action using LLM
        
        Args:
            ticket_text: The ticket text (subject + body)
        
        Returns:
            Dictionary with all 5 required outputs:
            1. Category
            2. Priority
            3. Department (Route to)
            4. Sentiment
            5. Recommended Next Action
        """
        
        # Step 1: ML Classification with confidence check
        ml_predictions, needs_llm_fallback, low_confidence_fields = \
            self.ml_predictor.predict_with_fallback_check(ticket_text)
        
        classification_source = 'ml'
        llm_fallback_used = False
        llm_fallback_error = None
        
        # Step 2: LLM Fallback for low-confidence predictions
        if needs_llm_fallback and self.llm_available:
            print(f"⚠️  Low confidence detected for: {', '.join(low_confidence_fields)}")
            print(f"   Routing to LLM for classification...")
            
            llm_classification_result = self.llm_client.classify_ticket_fallback(ticket_text)
            
            if llm_classification_result['success']:
                # Replace low-confidence ML predictions with LLM predictions
                for field in low_confidence_fields:
                    if field in llm_classification_result['predictions']:
                        ml_predictions[field] = llm_classification_result['predictions'][field]
                
                classification_source = 'hybrid'
                llm_fallback_used = True
                print(f"✓ LLM classification successful")
            else:
                llm_fallback_error = llm_classification_result.get('error')
                print(f"⚠️  LLM classification failed: {llm_fallback_error}")
                print(f"   Using ML predictions despite low confidence")
        
        # Step 3: Generate Recommended Next Action using LLM
        if self.llm_available:
            llm_result = self.llm_client.generate_next_action(ticket_text, ml_predictions)
            recommended_action = llm_result['recommended_action']
            llm_success = llm_result['success']
            llm_error = llm_result.get('error')
        else:
            # Fallback when LLM is not available
            recommended_action = self._generate_fallback_action(ml_predictions)
            llm_success = False
            llm_error = "LLM client not initialized"
        
        # Compile results
        result = {
            'ticket_text': ticket_text,
            
            # Classification Results
            'category': ml_predictions['category']['prediction'],
            'category_confidence': ml_predictions['category']['confidence'],
            
            'priority': ml_predictions['priority']['prediction'],
            'priority_confidence': ml_predictions['priority']['confidence'],
            
            'department': ml_predictions['department']['prediction'],
            'department_confidence': ml_predictions['department']['confidence'],
            
            'sentiment': ml_predictions['sentiment']['prediction'],
            'sentiment_confidence': ml_predictions['sentiment']['confidence'],
            
            # LLM Generation
            'recommended_action': recommended_action,
            'llm_success': llm_success,
            'llm_error': llm_error,
            
            # Hybrid approach metadata
            'classification_source': classification_source,  # 'ml', 'hybrid', or 'llm'
            'llm_fallback_used': llm_fallback_used,
            'low_confidence_fields': low_confidence_fields if needs_llm_fallback else [],
            
            # Full predictions for detailed view
            'detailed_predictions': ml_predictions
        }
        
        return result
    
    def process_batch(self, ticket_texts):
        """
        Process multiple tickets
        
        Args:
            ticket_texts: List of ticket texts
        
        Returns:
            List of result dictionaries
        """
        
        results = []
        
        for ticket_text in ticket_texts:
            result = self.process_ticket(ticket_text)
            results.append(result)
        
        return results
    
    def _generate_fallback_action(self, ml_predictions):
        """Generate fallback action when LLM is not available"""
        
        category = ml_predictions['category']['prediction']
        priority = ml_predictions['priority']['prediction']
        department = ml_predictions['department']['prediction']
        sentiment = ml_predictions['sentiment']['prediction']
        
        action = (
            f"Route this {category.lower()} to {department}. "
            f"Priority level: {priority}. "
            f"Customer sentiment: {sentiment}. "
            "Acknowledge receipt and begin investigation according to standard procedures. "
            "Request additional information if needed and keep customer updated on progress."
        )
        
        return action
    
    def change_llm_model(self, model):
        """Change the LLM model"""
        if self.llm_client:
            self.llm_client.change_model(model)
    
    def get_available_models(self):
        """Get available LLM models"""
        if self.llm_client:
            return self.llm_client.get_available_models()
        return []
    
    def get_system_info(self):
        """Get information about the system"""
        
        info = {
            'ml_predictor': self.ml_predictor.get_model_info(),
            'llm_available': self.llm_available,
            'llm_model': self.llm_client.model if self.llm_client else None,
            'confidence_threshold': self.ml_predictor.confidence_threshold,
            'approach': 'Hybrid (Sentence Transformers + XGBoost + LLM Fallback)'
        }
        
        return info

# Example usage
if __name__ == "__main__":
    
    print("="*80)
    print("TICKET PROCESSOR TEST - HYBRID APPROACH")
    print("="*80)
    
    # Initialize processor
    processor = TicketProcessor(confidence_threshold=0.65)
    
    # System info
    info = processor.get_system_info()
    print(f"\n✓ Ticket processor initialized")
    print(f"  Approach: {info['approach']}")
    print(f"  Confidence Threshold: {info['confidence_threshold']*100:.0f}%")
    print(f"  LLM Available: {info['llm_available']}")
    if info['llm_available']:
        print(f"  LLM Model: {info['llm_model']}")
    
    # Example tickets
    example_tickets = [
        {
            'title': 'VPN Connection Issue',
            'text': """
            Unable to connect VPN since morning, urgent client call in 20 mins.
            I've tried restarting my laptop and the VPN client but still getting 
            connection timeout errors. This is blocking critical work. Please help ASAP!
            """
        },
        {
            'title': 'Product Information Request',
            'text': """
            Hi, I would like to know more about your enterprise plan features.
            Specifically, I'm interested in the API rate limits, data retention policies,
            and available integrations. Could you send me detailed documentation?
            """
        },
        {
            'title': 'Billing Question',
            'text': """
            I noticed a duplicate charge on my account for $99.99. The charge appears
            twice on my March statement. Can you please investigate and refund if this
            was an error? My account ID is 12345.
            """
        }
    ]
    
    # Process each ticket
    for idx, ticket in enumerate(example_tickets, 1):
        print(f"\n{'='*80}")
        print(f"TICKET {idx}: {ticket['title']}")
        print('='*80)
        
        print(f"\nTicket Text:\n{ticket['text'].strip()}\n")
        
        # Process
        result = processor.process_ticket(ticket['text'])
        
        # Display results
        print("CLASSIFICATION RESULTS:")
        print("-"*80)
        
        confidence_flag = lambda c: "✓" if c >= 0.65 else "⚠️"
        
        print(f"1. Category:    {result['category']} {confidence_flag(result['category_confidence'])} (confidence: {result['category_confidence']*100:.1f}%)")
        print(f"2. Priority:    {result['priority']} {confidence_flag(result['priority_confidence'])} (confidence: {result['priority_confidence']*100:.1f}%)")
        print(f"3. Department:  {result['department']} {confidence_flag(result['department_confidence'])} (confidence: {result['department_confidence']*100:.1f}%)")
        print(f"4. Sentiment:   {result['sentiment']} {confidence_flag(result['sentiment_confidence'])} (confidence: {result['sentiment_confidence']*100:.1f}%)")
        
        # Show classification source
        print(f"\nClassification Source: {result['classification_source'].upper()}")
        if result['llm_fallback_used']:
            print(f"✓ LLM fallback used for: {', '.join(result['low_confidence_fields'])}")
        
        print(f"\n5. RECOMMENDED NEXT ACTION:")
        print("-"*80)
        print(result['recommended_action'])
        
        if not result['llm_success'] and result['llm_error']:
            print(f"\n⚠️  Note: Using fallback action (LLM error: {result['llm_error']})")
