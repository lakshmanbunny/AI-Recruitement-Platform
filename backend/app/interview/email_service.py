import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.email_from = settings.EMAIL_FROM
        self.app_base_url = settings.APP_BASE_URL

    async def send_interview_invite(self, candidate_id: str, candidate_name: str, candidate_email: str, room_id: str):
        """
        Sends an AI Interview invitation email using SMTP.
        """
        interview_url = f"{self.app_base_url}/interview/{room_id}"
        
        subject = "Paradigm AI Interview Invitation"
        
        html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                <h2 style="color: #1A1A1A;">Hello {candidate_name},</h2>
                <p>Congratulations! You have been invited to an AI-powered technical interview at <strong>Paradigm IT</strong>.</p>
                
                <div style="margin: 30px 0; text-align: center;">
                    <a href="{interview_url}" 
                       style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">
                       Join Interview Room
                    </a>
                </div>
                
                <p><strong>Instructions:</strong></p>
                <ul style="color: #4B5563;">
                    <li>Ensure you are in a quiet environment.</li>
                    <li>Check your microphone and camera settings.</li>
                    <li>The interview will be conducted by our AI recruiter.</li>
                </ul>
                
                <p style="margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px; color: #6B7280; font-size: 14px;">
                    Best regards,<br>
                    Recruitment Team<br>
                    Paradigm IT
                </p>
            </div>
        """

        msg = MIMEMultipart()
        msg['From'] = self.email_from
        msg['To'] = candidate_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        try:
            if not self.smtp_user or not self.smtp_password:
                logger.warning("SMTP credentials not set. Skipping email send (Simulation mode).")
                logger.info(f"SIMULATED EMAIL to {candidate_email}: {interview_url}")
                return True

            # Standard SMTP with STARTTLS
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email sent to {candidate_email} via SMTP")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {candidate_email} via SMTP: {str(e)}")
            return False
