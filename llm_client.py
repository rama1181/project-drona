"""
LLM Client Module
Integrates with Groq API for generating recommended next actions
"""

import os
from groq import Groq
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class GroqLLMClient:
    """Client for Groq LLM API"""
    
    def __init__(self, api_key=None, model=None):
        """
        Initialize Groq client
        
        Args:
            api_key: Groq API key (defaults to GROQ_API_KEY env var)
            model: Model to use (defaults to LLM_MODEL env var or llama-3.3-70b-versatile)
        """
        
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "Groq API key not found. Please set GROQ_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.client = Groq(api_key=self.api_key)
        self.model = model or os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
    
    def classify_ticket_fallback(self, ticket_text):
        """
        Use LLM to classify ticket when ML confidence is low
        
        Args:
            ticket_text: The ticket text to classify
        
        Returns:
            Dictionary with LLM classifications
        """
        
        prompt = f"""
You are an expert ticket classification system. Analyze the following customer support ticket and classify it into the appropriate categories.

**TICKET TEXT:**
{ticket_text}

**YOUR TASK:**
Classify this ticket into the following categories. Respond ONLY with valid JSON in the exact format shown below:

{{
  "category": "<Incident|Request|Problem|Change>",
  "priority": "<low|medium|high>",
  "department": "<Technical Support|Product Support|Customer Service|IT Support|Billing and Payments|Service Outages and Maintenance|Returns and Exchanges|Sales and Pre-Sales|Human Resources|General Inquiry>",
  "sentiment": "<Positive|Neutral|Negative|Urgent>"
}}

**CLASSIFICATION GUIDELINES:**

**Category:**
- Incident: Something is broken and needs immediate fixing
- Request: User is asking for information or a service
- Problem: Root cause investigation needed for recurring issues
- Change: Request to modify existing setup or configuration

**Priority:**
- high: Urgent, blocking work, critical business impact
- medium: Important but has workaround, moderate impact
- low: Minor issue, low impact, can wait

**Department:**
Choose the most appropriate team based on the issue type.

**Sentiment:**
- Urgent: Customer is frustrated, angry, or under time pressure
- Negative: Customer is dissatisfied but not urgent
- Neutral: Factual, neutral tone
- Positive: Customer is polite, appreciative, or satisfied

Respond with ONLY the JSON object, no additional text.
"""
        
        try:
            # Call Groq API
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert ticket classification system. "
                            "You MUST respond with ONLY valid JSON, no additional text or explanation."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.model,
                temperature=0.3,  # Lower temperature for more consistent classification
                max_tokens=200
            )
            
            # Extract response
            response_text = chat_completion.choices[0].message.content.strip()
            
            # Parse JSON response
            import json
            
            # Try to extract JSON if there's extra text
            if response_text.startswith('```'):
                # Remove markdown code blocks
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            classifications = json.loads(response_text)
            
            # Convert to prediction format with high confidence
            predictions = {}
            for field in ['category', 'priority', 'department', 'sentiment']:
                predictions[field] = {
                    'prediction': classifications.get(field, 'Unknown'),
                    'confidence': 0.95,  # LLM predictions treated as high confidence
                    'source': 'llm'
                }
            
            return {
                'success': True,
                'predictions': predictions,
                'model': self.model,
                'error': None
            }
        
        except Exception as e:
            # Return default classifications on error
            return {
                'success': False,
                'predictions': {
                    'category': {'prediction': 'Incident', 'confidence': 0.5, 'source': 'default'},
                    'priority': {'prediction': 'medium', 'confidence': 0.5, 'source': 'default'},
                    'department': {'prediction': 'Technical Support', 'confidence': 0.5, 'source': 'default'},
                    'sentiment': {'prediction': 'Neutral', 'confidence': 0.5, 'source': 'default'}
                },
                'model': self.model,
                'error': str(e)
            }
    
    def generate_resolution(self, ticket_subject, ticket_description, category, priority, department, sentiment, rag_similar_tickets=None):
        """
        Generate complete resolution including root cause, steps, escalation
        
        Args:
            ticket_subject: The ticket subject
            ticket_description: The ticket description
            category: Predicted category
            priority: Predicted priority
            department: Assigned department
            sentiment: Detected sentiment
            rag_similar_tickets: List of similar historical tickets (optional)
        
        Returns:
            Dictionary with root_cause, resolution_steps, escalation, etc.
        """
        
        # Build historical context
        historical_context = ""
        if rag_similar_tickets and len(rag_similar_tickets) > 0:
            historical_context = "\n=== SIMILAR HISTORICAL TICKETS ===\n"
            for match in rag_similar_tickets[:3]:
                t = match["ticket"]
                score = match["score"]
                historical_context += f"\nTicket #{t.get('ticket_id', '?')} (Similarity: {score:.1%})\n"
                historical_context += f"  Subject: {t.get('ticket_subject', 'N/A')}\n"
                historical_context += f"  Root Cause: {t.get('root_cause', 'N/A')}\n"
                historical_context += f"  Resolution: {t.get('resolution_steps', 'N/A')}\n"
        else:
            historical_context = "\n=== HISTORICAL CONTEXT ===\nNo similar tickets found in knowledge base. Provide general best-practice guidance.\n"
        
        prompt = f"""You are an experienced IT Service Desk Level 3 Support Engineer.

=== NEW TICKET ===
Subject: {ticket_subject}
Description: {ticket_description}

=== AI CLASSIFICATION ===
Category: {category}
Priority: {priority}
Department: {department}
Sentiment: {sentiment}
{historical_context}

Based on the above information, provide a complete resolution analysis.

**IMPORTANT:** Respond in this EXACT format:

Root Cause: [Provide the likely root cause based on symptoms]

Resolution Steps:
1. [First step with specific actions]
2. [Second step]
3. [Continue with clear, actionable steps]
[Maximum 8 steps, be specific and practical]

Escalation Required: [Yes or No]

Recommended Team: [Which team should handle this]

Respond in professional IT service desk format. Be concise and actionable."""
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert IT support engineer. Provide structured, professional ticket resolutions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.model,
                temperature=0.3,
                max_tokens=1024
            )
            
            response_text = chat_completion.choices[0].message.content
            
            # Parse the response
            return self._parse_resolution_response(response_text, department)
            
        except Exception as e:
            # Fallback to basic resolution
            return {
                'success': False,
                'root_cause': 'Unable to determine - AI analysis unavailable',
                'resolution_steps': self._get_fallback_resolution(category, priority),
                'full_response': f"AI resolution generation failed: {str(e)}\n\nFallback resolution provided.",
                'escalation_required': 'Yes' if priority in ['High', 'high'] else 'No',
                'recommended_team': department,
                'source': 'fallback',
                'error': str(e)
            }
    
    def _parse_resolution_response(self, response_text, default_department):
        """Parse the LLM resolution response"""
        import re
        
        root_cause = "Undetermined"
        resolution_steps = response_text.strip()
        escalation_required = "No"
        recommended_team = default_department
        
        # Extract Root Cause
        rc_match = re.search(r"Root Cause\s*[:：]\s*(.+?)(?:\n|Resolution Steps)", response_text, re.DOTALL | re.IGNORECASE)
        if rc_match:
            root_cause = rc_match.group(1).strip()
        
        # Extract Resolution Steps
        rs_match = re.search(r"Resolution Steps\s*[:：]?\s*((?:\n|\r\n?).+?)(?:Escalation Required|$)", response_text, re.DOTALL | re.IGNORECASE)
        if rs_match:
            resolution_steps = rs_match.group(1).strip()
        
        # Extract Escalation Required
        esc_match = re.search(r"Escalation Required\s*[:：]\s*(Yes|No)", response_text, re.IGNORECASE)
        if esc_match:
            escalation_required = esc_match.group(1).strip()
        
        # Extract Recommended Team
        rt_match = re.search(r"Recommended Team\s*[:：]\s*(.+?)(?:\n|$)", response_text, re.IGNORECASE)
        if rt_match:
            recommended_team = rt_match.group(1).strip()
        
        return {
            'success': True,
            'root_cause': root_cause,
            'resolution_steps': resolution_steps,
            'full_response': response_text.strip(),
            'escalation_required': escalation_required,
            'recommended_team': recommended_team,
            'source': 'groq_llm',
            'error': None
        }
    
    def _get_fallback_resolution(self, category, priority):
        """Generate basic fallback resolution"""
        
        fallback_resolutions = {
            'Incident': """1. Acknowledge the incident and gather detailed information
2. Check system logs and error messages
3. Attempt basic troubleshooting (restart service, clear cache)
4. If unresolved, escalate to senior support
5. Document all steps taken and findings""",
            'Request': """1. Verify request details and requester authorization
2. Check if request follows company policy
3. Process request according to standard procedures
4. Update requester on progress
5. Complete request and document outcome""",
            'Problem': """1. Review incident history and identify patterns
2. Conduct root cause analysis
3. Document findings and potential solutions
4. Test proposed solution in controlled environment
5. Implement permanent fix and monitor results""",
            'Change': """1. Review change request details and impact assessment
2. Get necessary approvals from change board
3. Schedule change during maintenance window
4. Execute change following documented procedure
5. Verify change success and update documentation"""
        }
        
        resolution = fallback_resolutions.get(category, fallback_resolutions['Incident'])
        
        if priority in ['High', 'high']:
            resolution = "**URGENT:** Immediate action required.\n\n" + resolution
        
        return resolution

    def generate_next_action(self, ticket_text, ml_predictions):
        """
        Generate recommended next action for a ticket
        
        Args:
            ticket_text: The ticket text
            ml_predictions: Dictionary with ML predictions (category, priority, department, sentiment)
        
        Returns:
            Dictionary with recommended action and explanation
        """
        
        # Extract predictions
        category = ml_predictions.get('category', {}).get('prediction', 'Unknown')
        priority = ml_predictions.get('priority', {}).get('prediction', 'Unknown')
        department = ml_predictions.get('department', {}).get('prediction', 'Unknown')
        sentiment = ml_predictions.get('sentiment', {}).get('prediction', 'Unknown')
        
        # Construct prompt
        prompt = self._create_prompt(ticket_text, category, priority, department, sentiment)
        
        try:
            # Call Groq API
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert customer support agent. Your role is to provide "
                            "clear, actionable, and empathetic recommendations for handling customer tickets. "
                            "Be professional, concise, and solution-oriented."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.model,
                temperature=0.7,
                max_tokens=500
            )
            
            # Extract response
            response_text = chat_completion.choices[0].message.content
            
            return {
                'success': True,
                'recommended_action': response_text,
                'model': self.model,
                'error': None
            }
        
        except Exception as e:
            return {
                'success': False,
                'recommended_action': self._get_fallback_action(category, priority, department),
                'model': self.model,
                'error': str(e)
            }
    
    def _create_prompt(self, ticket_text, category, priority, department, sentiment):
        """Create prompt for LLM"""
        
        prompt = f"""
You are analyzing a customer support ticket. Based on the ticket content and ML classification results, provide a recommended next action for the support agent.

**TICKET TEXT:**
{ticket_text}

**ML CLASSIFICATION RESULTS:**
- Category: {category}
- Priority: {priority}
- Department: {department}
- Sentiment: {sentiment}

**YOUR TASK:**
Provide a clear, actionable recommendation for how the support agent should handle this ticket. Your response should:

1. Acknowledge the customer's issue with empathy
2. Provide specific steps the agent should take
3. Include any information that should be requested from the customer
4. Suggest a timeline for resolution if applicable
5. Be professional and concise (3-5 sentences)

**RECOMMENDED NEXT ACTION:**
"""
        
        return prompt.strip()
    
    def _get_fallback_action(self, category, priority, department):
        """Generate fallback action when LLM fails"""
        
        fallback_actions = {
            ('Incident', 'high'): (
                "This is a high-priority incident requiring immediate attention. "
                "Acknowledge the issue immediately, escalate to senior support, and provide "
                "a timeline for investigation. Keep the customer updated every 2 hours."
            ),
            ('Incident', 'medium'): (
                "Acknowledge this incident and begin investigation within 4 hours. "
                "Request detailed logs and error messages from the customer. "
                "Provide an initial assessment within 24 hours."
            ),
            ('Request', 'high'): (
                "This is a high-priority request. Acknowledge receipt immediately and "
                "provide the requested information or resource within 4 hours. "
                "If additional clarification is needed, request it promptly."
            ),
            ('Request', 'medium'): (
                "Acknowledge this request and confirm you understand the requirements. "
                "Provide the requested information or resource within 24-48 hours. "
                "Set clear expectations for delivery."
            ),
            ('Problem', 'high'): (
                "This is a critical problem requiring investigation. Acknowledge immediately, "
                "gather diagnostic information, and involve technical specialists. "
                "Provide workaround if possible and commit to root cause analysis."
            ),
        }
        
        key = (category, priority)
        action = fallback_actions.get(key)
        
        if not action:
            action = (
                f"Acknowledge this {category.lower()} and route to {department}. "
                f"Given {priority} priority, respond within standard SLA timeframes. "
                "Request any additional information needed to resolve the issue."
            )
        
        return action
    
    def change_model(self, model):
        """Change the LLM model"""
        self.model = model
    
    def get_available_models(self):
        """Get list of available models"""
        return [
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma2-9b-it"
        ]

# Example usage
if __name__ == "__main__":
    
    print("="*80)
    print("LLM CLIENT TEST")
    print("="*80)
    
    # Check for API key
    api_key = os.environ.get("GROQ_API_KEY")
    
    if not api_key:
        print("\n❌ ERROR: GROQ_API_KEY environment variable not set")
        print("\nTo use this module, set your Groq API key:")
        print("  export GROQ_API_KEY='your-api-key-here'  # Linux/Mac")
        print("  set GROQ_API_KEY=your-api-key-here       # Windows CMD")
        print("  $env:GROQ_API_KEY='your-api-key-here'    # Windows PowerShell")
        print("\nGet your API key from: https://console.groq.com/")
    else:
        try:
            # Initialize client
            client = GroqLLMClient()
            
            print(f"\n✓ Groq client initialized")
            print(f"  Model: {client.model}")
            
            # Example ticket and predictions
            ticket_text = """
            Unable to connect VPN since morning, urgent client call in 20 mins.
            I've tried restarting my laptop and the VPN client but still getting connection timeout errors.
            This is blocking critical work. Please help ASAP!
            """
            
            ml_predictions = {
                'category': {'prediction': 'Incident'},
                'priority': {'prediction': 'high'},
                'department': {'prediction': 'Technical Support'},
                'sentiment': {'prediction': 'Urgent'}
            }
            
            print(f"\nTicket Text:\n{ticket_text.strip()}\n")
            print("ML Predictions:")
            for key, value in ml_predictions.items():
                print(f"  {key}: {value['prediction']}")
            
            # Generate recommendation
            print("\n" + "="*80)
            print("GENERATING RECOMMENDATION...")
            print("="*80)
            
            result = client.generate_next_action(ticket_text, ml_predictions)
            
            if result['success']:
                print("\n✓ Recommendation generated successfully\n")
                print("RECOMMENDED NEXT ACTION:")
                print("-"*80)
                print(result['recommended_action'])
            else:
                print(f"\n❌ LLM generation failed: {result['error']}")
                print("\nUsing fallback recommendation:")
                print("-"*80)
                print(result['recommended_action'])
        
        except Exception as e:
            print(f"\n❌ Error: {e}")
