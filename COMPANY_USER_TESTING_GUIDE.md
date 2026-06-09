# Company User Testing Guide

## 🎯 Quick Testing with Predefined Sample Tickets

The system now includes **10 ready-to-test sample tickets** that Company Users can select from a dropdown to instantly test the AI classification engine.

---

## 🔐 Company User Login Credentials

| Username | Password | Company Name |
|----------|----------|--------------|
| `tcs_user` | `tcs123` | TCS Global |
| `techcorp_user` | `techcorp123` | TechCorp Services |
| `innotech_user` | `innotech123` | InnoTech Ltd |
| `finbank_user` | `finbank123` | FinBank Corp |
| `medsys_user` | `medsys123` | MedSystems |
| `cloud_user` | `cloud123` | CloudSphere |
| `edulearn_user` | `edulearn123` | EduLearn Inc |
| `apex_user` | `apex123` | Apex Retail |

---

## 📋 10 Predefined Sample Tickets

### 1. 🚨 Critical: Production Database Down
**Category:** Incident  
**Expected Priority:** Critical  
**Expected Department:** Database Team / IT Support  
**Scenario:** Complete database outage affecting 50,000 users

### 2. 🔒 VPN Connection Issues
**Category:** Incident  
**Expected Priority:** High  
**Expected Department:** Technical Support / IT Support  
**Scenario:** Unable to connect to VPN, blocking remote work

### 3. 🐌 Slow Computer Performance
**Category:** Request / Incident  
**Expected Priority:** Medium  
**Expected Department:** Desktop Support / IT Support  
**Scenario:** Laptop running slow, affecting productivity

### 4. 👤 New Employee Access Request
**Category:** Request  
**Expected Priority:** Medium  
**Expected Department:** IT Support / Service Desk L1  
**Scenario:** New hire needs access to systems and drives

### 5. 🔑 Password Reset - Account Locked
**Category:** Request  
**Expected Priority:** High  
**Expected Department:** Service Desk L1 / IT Support  
**Scenario:** Forgotten password with locked account

### 6. 🖨️ Printer Malfunction - Paper Jam
**Category:** Incident  
**Expected Priority:** Medium  
**Expected Department:** Desktop Support / Technical Support  
**Scenario:** Office printer jammed affecting multiple users

### 7. 📧 Email Not Receiving Attachments
**Category:** Incident  
**Expected Priority:** High  
**Expected Department:** Technical Support / IT Support  
**Scenario:** Email security filter blocking legitimate attachments

### 8. ❓ Office 365 Features Question
**Category:** Request  
**Expected Priority:** Low  
**Expected Department:** Product Support / Customer Service  
**Scenario:** Information request about software capabilities

### 9. 🔐 Security: Suspicious Email Received
**Category:** Incident  
**Expected Priority:** High  
**Expected Department:** Technical Support / IT Support  
**Scenario:** Potential phishing email reported

### 10. 💻 Software Installation Request
**Category:** Request  
**Expected Priority:** Medium  
**Expected Department:** IT Support / Desktop Support  
**Scenario:** Adobe Creative Suite installation needed

---

## 🚀 How to Test

### Step 1: Start the Application
```bash
streamlit run app.py
```

### Step 2: Login as Company User
Use any of the company user credentials above, for example:
- **Username:** `techcorp_user`
- **Password:** `techcorp123`

### Step 3: Navigate to "Submit New Ticket" Tab
This is the default tab when you login.

### Step 4: Select a Sample Ticket
1. Look for the dropdown: **"Choose a pre-filled sample ticket to test the AI classification"**
2. Select any of the 10 sample tickets
3. The form will auto-populate with realistic ticket data:
   - Employee Name
   - Employee Email
   - Ticket Subject
   - Detailed Description

### Step 5: Submit the Ticket
Click the **"Submit Ticket"** button at the bottom of the form.

### Step 6: View AI Classification Results
The system will instantly show:

**🤖 Cognitive Analytics Summary:**
- **Routed Department** - Where the ticket was automatically sent
- **ML Priority** - Machine learning predicted priority
- **Keyword Priority** - Keyword-based priority detection
- **Final Priority** - Resolved priority (highest wins)
- **Predicted Category** - Incident/Request/Problem/Change
- **Customer Sentiment** - Positive/Neutral/Negative/Urgent

**📖 Retrieval-Augmented Recommendations:**
- Similarity match score (how similar to historical tickets)
- Root cause analysis
- Resolution steps
- Escalation requirements
- Recommended team
- Similar historical tickets

---

## 🧪 Testing Different Scenarios

### Test Critical Priority Escalation
Select: **"🚨 Critical: Production Database Down"**
- Should route to Database Team or IT Support
- Should be classified as Critical priority
- Should recommend immediate escalation
- Should detect Urgent sentiment

### Test Standard User Request
Select: **"👤 New Employee Access Request"**
- Should route to Service Desk L1 or IT Support
- Should be classified as Medium priority
- Should detect Neutral sentiment
- Should provide standard access provisioning steps

### Test Security Incident
Select: **"🔐 Security: Suspicious Email Received"**
- Should route to Technical Support or Security Team
- Should be classified as High priority
- Should detect potential security threat
- Should recommend security team involvement

### Test Low Priority Inquiry
Select: **"❓ Office 365 Features Question"**
- Should route to Product Support or Customer Service
- Should be classified as Low priority
- Should detect Neutral/Positive sentiment
- Should provide information resources

---

## 🔍 What to Observe

### 1. **ML Confidence Scores**
Look at the confidence percentages in the backend logs:
- ✅ High confidence (≥65%) = ML prediction used
- ⚠️ Low confidence (<65%) = LLM fallback triggered

### 2. **Hybrid Engine Performance**
Check if the system used:
- **ML only** - Fast classification with high confidence
- **ML + LLM Fallback** - ML had low confidence, Groq LLM provided classification
- **Recommended Action** - AI-generated next steps for support agents

### 3. **Priority Resolution**
Observe how the system combines:
- ML-predicted priority
- Keyword-based priority (e.g., "URGENT", "production down")
- Final priority (highest priority wins)

### 4. **RAG Similarity Search**
See how the system finds similar historical tickets:
- High similarity (>80%) = Strong match with past tickets
- Medium similarity (40-80%) = Partial match
- Low similarity (<40%) = Unique issue, potential outlier

### 5. **Gemini AI Resolution**
Check the quality of:
- Root cause analysis
- Resolution steps
- Escalation recommendations
- Team routing suggestions

---

## 📊 Expected Results by Sample

| Sample Ticket | Expected Category | Expected Priority | Expected Department |
|---------------|-------------------|-------------------|---------------------|
| Production Database Down | Incident | Critical | Database/IT Support |
| VPN Connection Issues | Incident | High | Technical Support |
| Slow Computer | Incident/Request | Medium | Desktop Support |
| New Employee Access | Request | Medium | Service Desk L1 |
| Password Reset | Request | High | Service Desk L1 |
| Printer Malfunction | Incident | Medium | Desktop Support |
| Email Attachments | Incident | High | Technical Support |
| Office 365 Question | Request | Low | Product Support |
| Security Email | Incident | High | Security/Tech Support |
| Software Installation | Request | Medium | IT Support |

---

## 🎓 Tips for Effective Testing

### 1. **Test All 10 Samples**
Each sample covers a different scenario to test various classification paths.

### 2. **Modify Sample Tickets**
After selecting a sample, you can edit the text to see how changes affect classification:
- Add urgency keywords → Priority may increase
- Change technical terms → Department routing may change
- Modify tone → Sentiment detection changes

### 3. **Compare ML vs LLM**
- Watch the console/logs for confidence scores
- Low confidence triggers LLM fallback
- High confidence uses pure ML (faster)

### 4. **Test Company SLA History**
- Submit multiple tickets
- Let some breach SLA (don't resolve them)
- Future tickets from that company may auto-escalate priority

### 5. **View Ticket Archive**
After submitting tickets:
1. Go to "Company Tickets Archive" tab
2. See all tickets for your company
3. Check status, priority, SLA compliance

---

## 🐛 Troubleshooting

### Dropdown Not Showing Samples?
- Refresh the page (press R in Streamlit)
- Ensure you're logged in as Company User (not Admin or Department User)

### AI Classification Not Working?
- Check if models are trained: `python train_xgboost_model.py`
- Verify models exist in `c:\project-drona\models\` folder
- Check for errors in the Streamlit console

### LLM Features Not Working?
- Add GROQ_API_KEY to your `.env` file
- System still works without it (uses ML fallback)
- Get key from: https://console.groq.com/

### Gemini Resolution Empty?
- Add GEMINI_API_KEY to your `.env` file
- Get key from: https://makersuite.google.com/app/apikey
- System falls back to RAG if Gemini unavailable

---

## 📈 Success Metrics

After testing, you should see:

✅ **Accurate Classification**
- Category matches the issue type
- Priority aligns with urgency
- Department routing is appropriate

✅ **Fast Response Time**
- ML classification: < 2 seconds
- LLM fallback: < 5 seconds
- Total pipeline: < 10 seconds

✅ **Quality Recommendations**
- Root cause makes sense
- Resolution steps are actionable
- Similar tickets are relevant

✅ **Confidence Scoring**
- Most tickets: High confidence (>65%)
- Edge cases: Low confidence, LLM triggered
- Consistent results on repeat tests

---

## 🎉 Quick Start Commands

```bash
# 1. Start the application
streamlit run app.py

# 2. Login credentials
Username: techcorp_user
Password: techcorp123

# 3. Select any sample ticket from dropdown
# 4. Click "Submit Ticket"
# 5. View AI classification results!
```

---

## 📝 Feedback & Improvements

After testing, note:
- Which classifications were accurate
- Which needed LLM fallback
- Any misrouted tickets
- Suggestions for new sample tickets

This feedback helps improve the ML models over time!

---

**Happy Testing!** 🚀
