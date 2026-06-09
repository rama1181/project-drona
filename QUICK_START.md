# 🚀 Quick Start Guide - Smart Ticket Understanding Engine

## ⚡ 5-Minute Setup & Test

### Step 1: Install Dependencies (First Time Only)
```bash
pip install -r requirements.txt
```

### Step 2: Configure API Keys
Create a `.env` file:
```bash
copy .env.example .env
```

Edit `.env` and add your keys:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

**Get API Keys:**
- Gemini: https://makersuite.google.com/app/apikey (Required)
- Groq: https://console.groq.com/ (Optional but recommended)

### Step 3: Models Already Trained? Skip to Step 5!
Check if models exist:
```bash
dir models
```

If you see `category_model.pkl`, `priority_model.pkl`, etc., skip training!

### Step 4: Train Models (Only if needed)
```bash
python train_xgboost_model.py
```
⏱️ Takes 3-5 minutes. You'll see progress bars and accuracy scores.

### Step 5: Start the Application
```bash
streamlit run app.py
```
🎉 Browser opens automatically at http://localhost:8501

---

## 🎯 Three Ways to Test

### Option A: Company User with Sample Tickets (Easiest!)

**1. Login as Company User:**
```
Username: techcorp_user
Password: techcorp123
```

**2. Select Sample Ticket:**
- See dropdown: "🎯 Quick Test with Sample Tickets"
- Choose: "🚨 High Priority: Production Database Down"
- Form auto-fills!

**3. Submit:**
- Click "Submit Ticket"
- Watch AI classify in real-time! ✨

**See Results:**
- ✅ Category: Incident
- ✅ Priority: High
- ✅ Department: Database Team
- ✅ Sentiment: Urgent
- ✅ Root Cause & Resolution
- ✅ Similar Historical Tickets

---

### Option B: Admin - Convert Email to Ticket

**1. Add Test Emails:**
```bash
python add_test_emails.py
```
✅ Adds 8 realistic test emails

**2. Login as Admin:**
```
Username: admin
Password: admin123
```

**3. Convert Email:**
- Go to "Gmail Simulation Gateway" tab
- Click "Convert Email to Ticket"
- AI processes it instantly!

---

### Option C: Test AI Classification Directly (No UI)

```bash
python test_ai_classification.py
```

See console output:
- ML predictions with confidence scores
- LLM fallback activation (if confidence low)
- AI-generated action recommendations
- All without opening browser!

---

## 📊 What You'll See

### For Every Ticket:

**🤖 AI Classifications:**
```
Category:    Incident          ✅ (89% confidence)
Priority:    High              ✅ (92% confidence)  
Department:  Database Team     ✅ (87% confidence)
Sentiment:   Urgent            ✅ (94% confidence)
```

**📖 AI Recommendations:**
```
Root Cause: Database connection pool exhausted
Resolution: 
  1. Restart database service
  2. Increase connection pool size
  3. Review query patterns for optimization
Escalation: Yes - Immediate senior team involvement
```

**🔍 Similar Tickets:**
```
Ticket #142 (85% match) - Previous database outage
Ticket #089 (72% match) - Connection pool issues
Ticket #234 (68% match) - Performance degradation
```

---

## 🎓 All User Accounts

### Admin (Full Access)
```
Username: admin
Password: admin123
```

### Company Users (Test Sample Tickets)
```
techcorp_user / techcorp123  → TechCorp Services
tcs_user / tcs123            → TCS Global
finbank_user / finbank123    → FinBank Corp
cloud_user / cloud123        → CloudSphere
medsys_user / medsys123      → MedSystems
innotech_user / innotech123  → InnoTech Ltd
edulearn_user / edulearn123  → EduLearn Inc
apex_user / apex123          → Apex Retail
```

### Department Users (Work on Tickets)
```
l1 / l1123              → Service Desk L1
infra / infra123        → Infra Team
desktop / desktop123    → Desktop Support
db / db123              → Database Team
security / security123  → Security Team
app / app123            → Application Support
```

---

## 🎯 10 Sample Tickets for Testing

| Icon | Sample Name | Category | Priority | Tests |
|------|-------------|----------|----------|-------|
| 🚨 | Production Database Down | Incident | High | Urgent escalation |
| 🔒 | VPN Connection Issues | Incident | High | Remote access |
| 🐌 | Slow Computer | Request | Medium | Performance |
| 👤 | New Employee Access | Request | Medium | Onboarding |
| 🔑 | Password Reset | Request | High | Quick fix |
| 🖨️ | Printer Malfunction | Incident | Medium | Hardware |
| 📧 | Email Attachments | Incident | High | Communication |
| ❓ | Office 365 Question | Request | Low | Information |
| 🔐 | Suspicious Email | Incident | High | Security |
| 💻 | Software Installation | Request | Medium | Standard request |

---

## 🔧 Troubleshooting

### Models Not Found?
```bash
python train_xgboost_model.py
```

### GROQ_API_KEY Warning?
System works without it but:
- Add to `.env` for LLM fallback
- Improves accuracy on edge cases
- Generates better action recommendations

### GEMINI_API_KEY Error?
Required for resolution generation:
- Get from: https://makersuite.google.com/app/apikey
- Add to `.env` file
- Restart app

### Port Already in Use?
```bash
streamlit run app.py --server.port 8502
```

### Browser Doesn't Open?
Manually go to: http://localhost:8501

---

## 📈 Success Checklist

After testing, you should see:

✅ App starts without errors  
✅ Login works for all user types  
✅ Sample tickets dropdown appears (Company User)  
✅ Form auto-fills when sample selected  
✅ Ticket submits successfully  
✅ AI classification completes in <10 seconds  
✅ Results show category, priority, department, sentiment  
✅ Root cause and resolution displayed  
✅ Similar tickets found (if historical data exists)  
✅ SLA timer starts automatically  
✅ Ticket appears in archive/dashboard  

---

## 💡 Pro Tips

### Test Different Scenarios
- Try all 10 sample tickets
- Modify text to see how classification changes
- Test with different company users
- Watch confidence scores in console

### Understand Hybrid Architecture
- High confidence (>65%) → Uses ML only (fast)
- Low confidence (<65%) → LLM fallback activated (accurate)
- Best of both worlds!

### Monitor Performance
- Check console for timing
- ML prediction: ~1-2 seconds
- LLM fallback: ~3-5 seconds
- Total pipeline: <10 seconds

### Improve Accuracy
- Retrain models with more data
- Adjust confidence threshold (default 65%)
- Add domain-specific training examples

---

## 🎬 Complete Workflow Demo

```bash
# Terminal 1: Add test data
python add_test_emails.py

# Terminal 2: Start app
streamlit run app.py

# Browser: Login as Company User
# Username: techcorp_user
# Password: techcorp123

# 1. Select sample: "🚨 High Priority: Production Database Down"
# 2. Click "Submit Ticket"
# 3. Observe AI classification
# 4. Note the results
# 5. Go to "Company Tickets Archive" tab
# 6. See your ticket listed!

# Try another user type
# Logout → Login as: admin / admin123
# Go to "Gmail Simulation Gateway"
# Convert an email → See same AI magic!
```

---

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | Complete project overview |
| `QUICK_START.md` | This file - fast setup |
| `COMPANY_USER_TESTING_GUIDE.md` | Detailed testing guide |
| `WHATS_NEW.md` | New features summary |
| `HOW_TO_POST_TICKETS.md` | All methods to create tickets |
| `MIGRATION_COMPLETE.md` | Migration from Mini_Project |
| `TESTING_VERIFICATION_GUIDE.md` | Comprehensive testing |

---

## 🚀 Next Steps

After successful testing:

1. **Customize Sample Tickets**
   - Edit `app.py` to add your own samples
   - Match your organization's ticket types

2. **Configure Real Gmail**
   - Follow instructions in `gmail_simulator.py`
   - Connect to actual Gmail inbox

3. **Build REST API**
   - See `HOW_TO_POST_TICKETS.md`
   - Enable external integrations

4. **Deploy to Production**
   - Use Streamlit Cloud or Docker
   - Set environment variables
   - Configure database persistence

5. **Train on Your Data**
   - Add your historical tickets to `Data/`
   - Retrain models: `python train_xgboost_model.py`
   - Improve accuracy for your use cases

---

## 🎉 You're Ready!

Everything is set up and ready to test. Start with:

```bash
streamlit run app.py
```

Login as `techcorp_user` / `techcorp123` and test the sample tickets!

**Questions?** Check the documentation files listed above.

**Happy Testing!** 🚀
