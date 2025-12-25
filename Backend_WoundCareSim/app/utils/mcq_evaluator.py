"""
MCQ Evaluation Utility
Validates student MCQ answers against Firestore ground truth.
Feeds results into Knowledge Agent scoring.
"""

from typing import Dict, List, Any, Optional


class MCQEvaluator:
    """
    Handles MCQ validation for Assessment step.
    Compares student answers with correct answers from Firestore.
    """
    
    @staticmethod
    def validate_mcq_answers(
        student_answers: Dict[str, str],
        correct_answers: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validates student MCQ responses against ground truth.
        
        Args:
            student_answers: Dict mapping question_id -> selected_option
                Example: {"q1": "A", "q2": "C"}
            correct_answers: Dict from Firestore containing:
                - questions: List of question objects with id, correct_answer
                
        Returns:
            MCQ evaluation result:
            - total_questions: int
            - correct_count: int
            - incorrect_count: int
            - unanswered_count: int
            - score: float (0.0-1.0)
            - per_question_feedback: List of feedback objects
        """
        questions = correct_answers.get("questions", [])
        total = len(questions)
        
        if total == 0:
            return {
                "total_questions": 0,
                "correct_count": 0,
                "incorrect_count": 0,
                "unanswered_count": 0,
                "score": 0.0,
                "per_question_feedback": []
            }
        
        correct = 0
        incorrect = 0
        unanswered = 0
        feedback_list = []
        
        for question in questions:
            q_id = question.get("id")
            correct_option = question.get("correct_answer")
            question_text = question.get("question", "")
            options = question.get("options", {})
            explanation = question.get("explanation", "")
            
            student_answer = student_answers.get(q_id)
            
            # Check if answered
            if not student_answer:
                unanswered += 1
                feedback_list.append({
                    "question_id": q_id,
                    "question_text": question_text,
                    "correct": False,
                    "student_answer": None,
                    "correct_answer": correct_option,
                    "correct_answer_text": options.get(correct_option, ""),
                    "feedback": "Question not answered",
                    "explanation": explanation
                })
                continue
            
            # Validate answer
            is_correct = student_answer.upper() == correct_option.upper()
            
            if is_correct:
                correct += 1
                feedback_list.append({
                    "question_id": q_id,
                    "question_text": question_text,
                    "correct": True,
                    "student_answer": student_answer,
                    "correct_answer": correct_option,
                    "student_answer_text": options.get(student_answer, ""),
                    "feedback": "Correct answer",
                    "explanation": explanation
                })
            else:
                incorrect += 1
                feedback_list.append({
                    "question_id": q_id,
                    "question_text": question_text,
                    "correct": False,
                    "student_answer": student_answer,
                    "correct_answer": correct_option,
                    "student_answer_text": options.get(student_answer, ""),
                    "correct_answer_text": options.get(correct_option, ""),
                    "feedback": f"Incorrect. The correct answer is {correct_option}",
                    "explanation": explanation
                })
        
        # Calculate score
        score = correct / total if total > 0 else 0.0
        
        return {
            "total_questions": total,
            "correct_count": correct,
            "incorrect_count": incorrect,
            "unanswered_count": unanswered,
            "score": score,
            "per_question_feedback": feedback_list
        }
    
    @staticmethod
    def compute_mcq_contribution(mcq_score: float, weight: float = 0.4) -> float:
        """
        Computes MCQ contribution to Knowledge Agent score.
        
        Args:
            mcq_score: MCQ validation score (0.0-1.0)
            weight: How much MCQ affects Knowledge score (default 40%)
        
        Returns:
            Weighted MCQ contribution
        """
        return mcq_score * weight
    
    @staticmethod
    def get_mcq_summary(mcq_result: Dict[str, Any]) -> str:
        """
        Generates human-readable MCQ performance summary.
        
        Args:
            mcq_result: Output from validate_mcq_answers
        
        Returns:
            Summary string
        """
        total = mcq_result.get("total_questions", 0)
        correct = mcq_result.get("correct_count", 0)
        score = mcq_result.get("score", 0.0)
        
        if total == 0:
            return "No MCQ questions available"
        
        percentage = score * 100
        
        if score >= 0.8:
            performance = "Excellent"
        elif score >= 0.6:
            performance = "Good"
        elif score >= 0.4:
            performance = "Fair"
        else:
            performance = "Needs improvement"
        
        return f"{performance}: {correct}/{total} correct ({percentage:.0f}%)"