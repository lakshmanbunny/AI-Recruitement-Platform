import os
from config.logging_config import get_logger

logger = get_logger(__name__)

def send_interview_invite(candidate_email: str, session_link: str, candidate_name: str) -> bool:
    """
    Sends a secure interview invitation email using SendGrid.
    """
    # Note: In a production environment, this would integrate with SendGrid API.
    # For now, we simulate the email sending to standard logging.
    
    email_subject = "Action Required: Your Technical Interview Invitation"
    email_body = f"""
    Dear {candidate_name},
    
    You have successfully passed the initial enterprise RAG screening.
    
    We would like to invite you to the next step of the process: a dynamic technical interview.
    Please join the secure interview session using the link below:
    
    {session_link}
    
    IMPORTANT: 
    - This link is unique to you and will expire in 24 hours.
    - Ensure your camera and microphone are working before joining.
    
    Best regards,
    The AI Recruitment Team
    """
    
    # Simulated SendGrid send
    logger.info(f"========== SENDGRID EMAIL DISPATCH ==========")
    logger.info(f"To: {candidate_email}")
    logger.info(f"Subject: {email_subject}")
    logger.info(f"Body: {email_body}")
    logger.info(f"=============================================")
    
    return True
