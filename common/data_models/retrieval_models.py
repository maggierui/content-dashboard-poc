from dataclasses import dataclass, field, asdict
import json
from typing import List, Optional
import uuid


@dataclass
class RetrievedChunk:
    """Represents a retrieved content chunk."""
    chunk_id: str
    url: str
    content: str

    @staticmethod
    def create(content: str, url: str) -> "RetrievedChunk":
        return RetrievedChunk(
            chunk_id=str(uuid.uuid4()),
            url=url,
            content=content
        )


@dataclass
class ChunkRelevance:
    """Relevance assessment for chunks associated with a question."""
    score: float = 0.0
    strengths: str = ""
    weaknesses: str = ""


@dataclass
class UnansweredQuestionResult:
    """Combined result for a single unanswered question: gap analysis + retrieval verdict."""
    question: str
    why_expected: str
    gap_type: str
    overall_verdict: str = ""
    rationale: List[str] = field(default_factory=list)
    relevant_chunks: List[RetrievedChunk] = field(default_factory=list)


@dataclass
class ArticleUnansweredResult:
    """Combined unanswered-questions result for a single article."""
    full_path: str
    questions: List[UnansweredQuestionResult] = field(default_factory=list)

    def save(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    @staticmethod
    def save_all(results: List["ArticleUnansweredResult"], file_path: str) -> None:
        data = [asdict(r) for r in results]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


@dataclass
class RetrievalQuestion:
    """Represents a question and its associated chunks."""
    question_id: str
    question: str
    chunks: List[RetrievedChunk] = field(default_factory=list)
    retrieved: bool = False
    chunk_relevance: Optional[ChunkRelevance] = None

    @staticmethod
    def create(question: str) -> "RetrievalQuestion":
        return RetrievalQuestion(
            question_id=str(uuid.uuid4()),
            question=question
        )


@dataclass
class ArticlePerformance:
    """Represents an article and its associated questions."""
    article_id: str
    content: str
    full_path: str = ""
    relevant_path: str = ""
    questions: List[RetrievalQuestion] = field(default_factory=list)
    score: float = 0.0

    @staticmethod
    def create(content: str, full_path: str = "") -> "ArticlePerformance":
        return ArticlePerformance(
            article_id=str(uuid.uuid4()),
            content=content,
            full_path=full_path
        )
    
    def save(self, file_path: str) -> None:
        """Save this article performance to a JSON file."""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    @staticmethod
    def load(file_path: str) -> "ArticlePerformance":
        """Load a single article performance from a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ArticlePerformance._from_dict(data)

    @staticmethod
    def save_all(performances: List["ArticlePerformance"], file_path: str) -> None:
        """Save a list of article performances to a JSON file."""
        data = [asdict(p) for p in performances]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load_all(file_path: str) -> List["ArticlePerformance"]:
        """Load a list of article performances from a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [ArticlePerformance._from_dict(item) for item in data]

    @staticmethod
    def _from_dict(data: dict) -> "ArticlePerformance":
        """Reconstruct ArticlePerformance from a dictionary."""
        questions = [
            RetrievalQuestion(
                question_id=q["question_id"],
                question=q["question"],
                retrieved=q["retrieved"],
                chunks=[RetrievedChunk(**c) for c in q["chunks"]],
                chunk_relevance=ChunkRelevance(**q["chunk_relevance"]) if q.get("chunk_relevance") else None
            )
            for q in data.get("questions", [])
        ]
        return ArticlePerformance(
            article_id=data["article_id"],
            content=data["content"],
            full_path=data.get("full_path", ""),
            relevant_path=data.get("relevant_path", ""),
            questions=questions,
            score=data.get("score", 0.0)
        )