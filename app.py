import streamlit as st
from pymongo import MongoClient
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime
import pandas as pd
import bcrypt
import os
from dotenv import load_dotenv
from PyPDF2 import PdfReader

# ================= PAGE CONFIG =================
st.set_page_config(page_title="MentorBridge AI", layout="wide")

# ================= WHITE/LIGHT THEME =================
st.markdown("""
<style>
/* Main app background */
.stApp {
    background-color: #ffffff;
    color: #1f2937;  /* dark gray text for readability */
}

/* Sidebar styling */
section[data-testid="stSidebar"] {
    background-color: #f9fafb;
    color: #1f2937;
    border-right: 1px solid #e5e7eb;
}

/* Buttons */
.stButton>button {
    background: linear-gradient(90deg,#2563eb,#4f46e5);
    color: white;
    border-radius: 6px;
    height: 38px;
    border: none;
}

/* Input boxes and text areas */
input, textarea, .stTextInput>div>input, .stTextArea>div>textarea {
    background-color: #ffffff !important;
    color: #1f2937 !important;
    border: 1px solid #d1d5db !important;
    border-radius: 6px !important;
}

/* Cards */
.card {
    background: #ffffff;
    padding: 15px;
    border-radius: 10px;
    margin-bottom: 10px;
    border: 1px solid #e5e7eb;
    color: #1f2937;
}

/* Tables */
.stDataFrame, .stTable {
    background-color: #ffffff;
    color: #1f2937;
}

/* Headers */
h1, h2, h3, h4, h5, h6 {
    color: #111827;
}
</style>
""", unsafe_allow_html=True)

# ================= LOAD ENV =================
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    st.error("MongoDB URI missing in .env")
    st.stop()

client = MongoClient(MONGO_URI)
db = client["mentorbridge"]

users = db["users"]
requests = db["requests"]
messages = db["messages"]
internships = db["internships"]

# ================= INDUSTRY DATA =================
INDUSTRY_SKILLS = {
    "Data Scientist": ["Python","SQL","Machine Learning","Statistics","Deep Learning"],
    "Backend Developer": ["Python","Django","APIs","Databases","Cloud"],
    "AI Engineer": ["Python","Machine Learning","Deep Learning","NLP","MLOps"]
}

# ================= PASSWORD =================
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def check_password(password, hashed):
    if isinstance(hashed, str):
        hashed = hashed.encode()
    return bcrypt.checkpw(password.encode(), hashed)

# ================= DEFAULT ADMIN =================
if not users.find_one({"email":"admin@mentorbridge.com"}):
    users.insert_one({
        "name":"Super Admin",
        "email":"admin@mentorbridge.com",
        "password":hash_password("admin123"),
        "role":"Admin",
        "created_at":datetime.now()
    })

# ================= SESSION =================
if "user" not in st.session_state:
    st.session_state.user = None

# ================= LOGIN / REGISTER =================
if not st.session_state.user:

    st.title("🚀 MentorBridge AI")

    option = st.radio("Choose Option", ["Login","Register"])

    if option == "Register":
        name = st.text_input("Name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        role = st.selectbox("Role", ["Student","Mentor"])

        if st.button("Register"):
            if users.find_one({"email":email}):
                st.error("Email already exists")
            else:
                users.insert_one({
                    "name":name,
                    "email":email,
                    "password":hash_password(password),
                    "role":role,
                    "skills":[],
                    "career_goal":"",
                    "expertise":"",
                    "experience":0,
                    "bio":"",
                    "created_at":datetime.now()
                })
                st.success("Registered Successfully")

    if option == "Login":
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            user = users.find_one({"email":email})
            if user and check_password(password,user["password"]):
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid Credentials")

# ================= LOGGED IN =================
else:

    user = st.session_state.user
    role = user["role"]

    st.sidebar.write(f"👤 {user['name']} ({role})")

    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.rerun()

    # ================= ADMIN =================
    if role == "Admin":

        st.title("📊 Admin Dashboard")

        col1,col2,col3 = st.columns(3)
        col1.metric("Total Users", users.count_documents({}))
        col2.metric("Students", users.count_documents({"role":"Student"}))
        col3.metric("Mentors", users.count_documents({"role":"Mentor"}))

        st.subheader("All Users")
        for u in users.find():
            st.write(f"{u['name']} - {u['role']}")

    # ================= STUDENT =================
    elif role == "Student":

        menu = st.sidebar.radio("Navigation",[
            "Profile",
            "AI Mentor Matching",
            "Internship Matching",
            "Skill Gap",
            "Career Roadmap",
            "Mentorship Requests",
            "Chat"
        ])

        # ===== PROFILE =====
        if menu == "Profile":
            skills = st.text_input("Skills (comma separated)", value=", ".join(user.get("skills",[])))
            career_goal = st.text_input("Career Goal", value=user.get("career_goal",""))
            bio = st.text_area("Bio", value=user.get("bio",""))

            if st.button("Update"):
                users.update_one({"_id":user["_id"]},
                                 {"$set":{
                                     "skills":[s.strip() for s in skills.split(",") if s.strip()],
                                     "career_goal":career_goal,
                                     "bio":bio
                                 }})
                st.success("Profile Updated")
                st.rerun()

        # ===== AI MENTOR MATCHING =====
        elif menu == "AI Mentor Matching":

            mentors = list(users.find({"role":"Mentor"}))
            for mentor in mentors:
                score = 0
                if user.get("skills") and mentor.get("skills"):
                    docs = [" ".join(user["skills"]),
                            " ".join(mentor["skills"])]
                    vectors = CountVectorizer().fit_transform(docs).toarray()
                    similarity = cosine_similarity([vectors[0]],[vectors[1]])[0][0]
                    score += similarity

                st.markdown(f"<div class='card'><b>{mentor['name']}</b><br>Match Score: {round(score,2)}</div>", unsafe_allow_html=True)

        # ===== INTERNSHIP MATCHING =====
        elif menu == "Internship Matching":
            for job in internships.find():
                score = 0
                if user.get("skills") and job.get("required_skills"):
                    docs = [" ".join(user["skills"]),
                            " ".join(job["required_skills"])]
                    vectors = CountVectorizer().fit_transform(docs).toarray()
                    similarity = cosine_similarity([vectors[0]],[vectors[1]])[0][0]
                    score = similarity

                st.markdown(f"<div class='card'><b>{job['title']}</b><br>Match Score: {round(score,2)}</div>", unsafe_allow_html=True)

        # ===== SKILL GAP =====
        elif menu == "Skill Gap":
            goal = user.get("career_goal","")
            if goal in INDUSTRY_SKILLS:
                required = set(INDUSTRY_SKILLS[goal])
                current = set(user.get("skills",[]))
                missing = list(required - current)
                completion = int((len(required & current)/len(required))*100)

                st.write("Missing Skills:", missing)
                st.progress(completion)
            else:
                st.info("Set career goal first.")

        # ===== CAREER ROADMAP =====
        elif menu == "Career Roadmap":
            goal = user.get("career_goal","")
            if goal in INDUSTRY_SKILLS:
                for i,skill in enumerate(INDUSTRY_SKILLS[goal],1):
                    st.write(f"Step {i}: Learn {skill}")
            else:
                st.info("Update career goal.")

        # ===== REQUESTS =====
        elif menu == "Mentorship Requests":
            for req in requests.find({"student":user["name"]}):
                st.write(req)

        # ===== CHAT =====
        elif menu == "Chat":
            approved = list(requests.find({"student":user["name"],"status":"Approved"}))
            mentors=[a["mentor"] for a in approved]
            if mentors:
                selected = st.selectbox("Select Mentor", mentors)
                chat_data = messages.find({
                    "$or":[
                        {"sender":user["name"],"receiver":selected},
                        {"sender":selected,"receiver":user["name"]}
                    ]
                })
                for msg in chat_data:
                    st.write(f"{msg['sender']}: {msg['message']}")
                msg = st.text_input("Message")
                if st.button("Send"):
                    messages.insert_one({
                        "sender":user["name"],
                        "receiver":selected,
                        "message":msg,
                        "timestamp":datetime.now()
                    })
                    st.rerun()

    # ================= MENTOR =================
    elif role == "Mentor":

        menu = st.sidebar.radio("Navigation",[
            "Profile",
            "Pending Requests",
            "Chat"
        ])

        # ===== PROFILE =====
        if menu == "Profile":
            skills = st.text_input("Skills", value=", ".join(user.get("skills",[])))
            expertise = st.text_input("Expertise", value=user.get("expertise",""))
            experience = st.number_input("Experience", value=user.get("experience",0))

            if st.button("Update"):
                users.update_one({"_id":user["_id"]},
                                 {"$set":{
                                     "skills":[s.strip() for s in skills.split(",") if s.strip()],
                                     "expertise":expertise,
                                     "experience":experience
                                 }})
                st.success("Profile Updated")
                st.rerun()

        # ===== PENDING REQUESTS =====
        elif menu == "Pending Requests":
            for req in requests.find({"mentor":user["name"]}):
                st.write(req)
                if req["status"]=="Pending":
                    col1,col2 = st.columns(2)
                    if col1.button(f"Approve {req['_id']}"):
                        requests.update_one({"_id":req["_id"]},{"$set":{"status":"Approved"}})
                        st.rerun()
                    if col2.button(f"Reject {req['_id']}"):
                        requests.update_one({"_id":req["_id"]},{"$set":{"status":"Rejected"}})
                        st.rerun()

        # ===== CHAT =====
        elif menu == "Chat":
            approved = list(requests.find({"mentor":user["name"],"status":"Approved"}))
            students=[a["student"] for a in approved]
            if students:
                selected = st.selectbox("Select Student", students)
                chat_data = messages.find({
                    "$or":[
                        {"sender":user["name"],"receiver":selected},
                        {"sender":selected,"receiver":user["name"]}
                    ]
                })
                for msg in chat_data:
                    st.write(f"{msg['sender']}: {msg['message']}")
                msg = st.text_input("Message")
                if st.button("Send"):
                    messages.insert_one({
                        "sender":user["name"],
                        "receiver":selected,
                        "message":msg,
                        "timestamp":datetime.now()
                    })
                    st.rerun()
