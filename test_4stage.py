#!/usr/bin/env python3
"""Quick test of 4-stage scoring pipeline."""

import json
from llm.unified_scorer import UnifiedScorer

# Test data
test_content = """
DevOps Engineer - Remote

Tech stack:
- Python, Bash
- Docker, Kubernetes
- Terraform, Ansible
- GCP, AWS
- CI/CD (GitLab, GitHub Actions)

Requirements:
- 3+ years DevOps experience
- Strong Linux/Unix skills
- Experience with container orchestration
- IaC knowledge (Terraform preferred)

We offer:
- 100% remote work
- 20-25k PLN/month B2B
- Training budget (conferences, certifications)
- Modern tech stack
- Flat hierarchy
"""

test_metadata = {
    "company": "TechCorp",
    "title": "DevOps Engineer",
    "location": "Warsaw",
    "remote_mode": "remote",
    "contract_type": "b2b",
    "salary_min": 20000,
    "salary_max": 25000,
    "salary_currency": "PLN",
}

def test_4stage():
    print("🔧 Initializing scorer...")
    scorer = UnifiedScorer()

    print("🚀 Running 4-stage analysis...")
    print("")

    try:
        result = scorer.score_offer(
            content=test_content,
            metadata=test_metadata,
            existing_tags=["python", "docker", "kubernetes", "terraform", "ansible", "gcp", "aws"]
        )

        print("=" * 60)
        print("STAGE 1: TAGGING & SUMMARY")
        print("=" * 60)
        print(f"Language: {result['language']}")
        print(f"Tags: {', '.join(result['extracted_tags'][:10])}...")
        print(f"Summary: {result['short_summary']}")
        print("")

        print("=" * 60)
        print("STAGE 2: RISK ANALYSIS")
        print("=" * 60)
        print(f"Januszex Score: {result['januszex_score']:.0f}/100")
        print(f"Work Culture: {result['work_culture_score']:.0f}/100")
        print(f"Stability: {result['stability_score']:.0f}/100")
        print(f"Cringe: {result['cringe_score']:.0f}/100")
        print(f"Risk Reasoning: {result['risk_reasoning']}")
        print("")

        print("=" * 60)
        print("STAGE 3: FIT ANALYSIS")
        print("=" * 60)
        print(f"Fit Score: {result['fit_score']:.0f}/100")
        print(f"Matched Tags: {', '.join(result['fit_tags_matched'])}")
        print(f"Missing Tags: {', '.join(result['fit_tags_missing'])}")
        print(f"Avoided Tags: {', '.join(result['fit_tags_avoided'])}")
        print(f"Fit Reasoning: {result['fit_reasoning']}")
        print("")

        print("=" * 60)
        print("STAGE 4: FINAL DECISION")
        print("=" * 60)
        print(f"Decision: {result['decision']}")
        print(f"Final Score: {result['final_score']:.0f}/100")
        print(f"Confidence: {result['confidence']}")
        print(f"Decision Reasoning: {result['decision_reasoning']}")
        print("")

        print("=" * 60)
        print("✅ TEST PASSED - All 4 stages completed!")
        print("=" * 60)

        # Save full output
        with open("/tmp/test_4stage_output.json", "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("\n💾 Full output saved to: /tmp/test_4stage_output.json")

        return True

    except Exception as e:
        print("=" * 60)
        print("❌ TEST FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    success = test_4stage()
    sys.exit(0 if success else 1)
