# backend/persona.py

"""
Defines a "persona" for the AI interviewee.  The Conversation code expects:

    persona.name
    persona.education.year
    persona.education.institution
    persona.education.degree
    persona.technical.languages       (list of strings)
    persona.technical.skills          (list of strings)
    persona.technical.projects        (list of strings)
    persona.personality.interests     (list of strings)
    persona.personality.goals         (list of strings)
"""

from types import SimpleNamespace

# ──────────────────────────────────────────────────────────────────────
# Yatharth Sameer's comprehensive resume information
# ──────────────────────────────────────────────────────────────────────

persona = SimpleNamespace(
    name="Yatharth Sameer",
    education=SimpleNamespace(
        year=4,  # Dual Degree student
        institution="Indian Institute of Technology Kharagpur",
        degree="Dual Degree (B.Tech + M.Tech) in Computer Science and Engineering",
        gpa="9.04/10.00",
    ),
    technical=SimpleNamespace(
        languages=[
            "Go",
            "C++17",
            "Python",
            "Java",
            "TypeScript",
            "SQL",
            "MySQL",
            "Postgres",
            "NoSQL",
        ],
        skills=[
            "Full-Stack Development",
            "Distributed Systems",
            "MLOps",
            "CI/CD",
            "API Design",
            "Scalability",
            "Spring Boot",
            "React",
            "Next.js",
            "Angular",
            "Elasticsearch",
            "Docker",
            "Kubernetes",
            "FPGA",
            "Agile",
            "GCP (BigQuery, Cloud Run, GKE)",
            "AWS (S3, ECS, SageMaker)",
            "PyTorch",
            "Transformers",
            "Linux",
            "gRPC",
            "TCP/IP",
            "Machine Learning",
            "OOP",
            "DSA",
            "OS",
            "GitHub Actions",
            "OpenTelemetry",
            "GraphQL",
            "MongoDB",
            "Kafka",
            "Cloud Run",
            "BigQuery",
            "Looker",
            "SageMaker",
            "CloudWatch",
        ],
        projects=[
            "JusticeSearch – Scalable Legal Search Engine (Golang, MongoDB, Kafka)",
            "NeuralCoder – GPT-4 fine-tuned assistant for CP problems",
            "IVR Stress-Test Platform at Sprinklr (Java, Spring Boot, Angular)",
            "Multi-tenant AI Hiring Platform at Mercor (React, Go, GKE, MongoDB)",
            "Real-time Analytics Hub at Mercor (BigQuery, Looker)",
            "GPT-based Resume Parser on SageMaker",
            "A/B Testing Pipeline at Merlin AI (Cloud Run, BigQuery)",
            "AI Copy Generator at Narrato AI (GraphQL, OpenTelemetry)",
            "Epoll-based Go Load Balancer",
            "Tone-matching AI Email Assistant",
        ],
    ),
    personality=SimpleNamespace(
        interests=[
            "Distributed Systems",
            "Machine Learning",
            "System Design",
            "Competitive Programming",
            "Open Source",
            "Cloud Infrastructure",
            "Performance Optimization",
            "Real-time Systems",
            "AI/ML Engineering",
            "Backend Architecture",
        ],
        goals=[
            "Build scalable production systems",
            "Contribute to developer communities",
            "Work on challenging technical problems",
            "Drive innovation in AI and ML systems",
            "Mentor and help others grow",
            "Optimize system performance",
            "Create impactful products",
        ],
        achievements=[
            "AIR 423 in JEE Advanced 2020 among 2M+ candidates",
            "AIR 1123 in JEE Mains 2020",
            "Candidate Master on Codeforces (max rating 1950)",
            "5-star rated coder (2200+) on Codechef",
            "Global rank 790 in Google Hashcode 2022",
            "Qualified for Round 2 of Meta HackerCup 2022",
            "Amazon ML Summer School 2024 among 67K+ candidates",
        ],
        experience=[
            "Product Engineer Intern at Sprinklr (Apr 2024 – Aug 2024)",
            "Founding Software Engineer Intern at Mercor (Mar 2022 – Mar 2024)",
            "Software Engineer Intern at Merlin AI (Dec 2021 – Feb 2022)",
            "Software Engineer Intern at Narrato AI (Apr 2021 – Aug 2021)",
        ],
    ),
)
