"""제목 키워드 공통 규칙 (categorize.py). 예시는 2026-11-14 실제 NYU / Princeton 행사 제목."""
import pytest

from ingest.categorize import from_title


@pytest.mark.parametrize("title, expected", [
    ("(11/27/26) Thanksgiving Holiday (No Classes)", "ACADEMIC"),
    ("Spring Registration Begins", "ACADEMIC"),
    ("Fall 2026 Withdrawal Deadline - All Courses", "ACADEMIC"),
    ("Inditex/ZARA Early Careers Information Session", "CAREER"),
    ("GIP x PEG x CEC Private Equity Panel", "CAREER"),
    ("Resume Workshop: Building a Resume That Gets Noticed", "CAREER"),
    ("Mindfulness-Based Vinyasa Yoga with Hunt Parr", "WELLNESS"),
    ("Flu Pop-Up Clinic at the NEST", "WELLNESS"),
    ("NYU Symphony Orchestra", "ARTS"),
    ("Film Screening and Discussion: They Remember", "ARTS"),
    ("Chamber Music With Piano", "ARTS"),
    ("Research Seminar: Alessandro Rizzo", "ACADEMIC"),
    ("PhD Dissertation Defense: Estimating Pile Bearing Capacity", "ACADEMIC"),
    ("Supplemental Learning Group - Organic Chemistry I", "ACADEMIC"),
    ("New York Rangers V. New Jersey Devils", "SPORTS"),
    ("Brother's 3v3 Basketball Tournament", "SPORTS"),
    ("Abercrombie & Fitch v. Hunting World", None),           # 법률 사건명은 경기가 아님
    ("Star Wars Republic vs Roman Empire Trivia Night!", "SOCIAL"),
    ("Lutheran Campus Ministry Table Talk", "SOCIAL"),
    ("Princeton Christian Fellowship Bible studies", "SOCIAL"),
    ("Magic: The Gathering Club Meeting", "SOCIAL"),
    ("Tisch International Student Thanksgiving Dinner", "SOCIAL"),
    ("Qur’an Circle with Brother Tamim Islam", "SOCIAL"),
    ("Meet Up & Read Up", "SOCIAL"),
    ("Vitalisms II", None),
])
def test_from_title(title, expected):
    assert from_title(title) == expected
