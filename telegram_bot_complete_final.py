
#!/usr/bin/env python3
"""
Telegram Virtual Phone Number Bot - Complete Final Version
Tạo số điện thoại riêng tư và nhận SMS thật/mô phỏng

✨ TÍNH NĂNG:
• Tạo số điện thoại hoàn toàn riêng tư
• NhYOUR_SMS_ACTIVATE_API_KEY_HEREận SMS thật từ các dịch vụ API (SMS-Activate, 5sim)
• SMS mô phỏng tự động cho user thường
• Phân quyền Admin/User với giới hạn
• Hỗ trợ 10+ quốc gia

🔧 CÀI ĐẶT:
1. pip install python-telegram-bot requests
2. Thay thế API keys bên dưới (nếu muốn SMS thật)
3. python telegram_bot_complete_final.py

👑 ADMIN: User ID 6334711569 (tự động có quyền admin)
🤖 BOT TOKEN: 7491923931:AAF0obdJEViEb2loVwzoTW3YlQc5mWCZ6po

🔑 ĐỂ SỬ DỤNG SMS THẬT:
- Thay 'YOUR_SMS_ACTIVATE_API_KEY_HERE' bằng API key thật
- Thay 'YOUR_FIVESIM_API_KEY_HERE' bằng API key thật
- Hoặc set biến môi trường SMS_ACTIVATE_API_KEY và FIVESIM_API_KEY
"""

import asyncio
import logging
import os
import json
import random
import threading
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "7491923931:AAF0obdJEViEb2loVwzoTW3YlQc5mWCZ6po"
ADMIN_USER_ID = 6334711569

# =============================================================================
# USER MANAGER CLASS
# =============================================================================

class UserManager:
    def __init__(self, users_file: str = "data/users.json"):
        self.users_file = users_file
        self._ensure_data_directory()
        self.users = self._load_users()
    
    def _ensure_data_directory(self):
        """Ensure data directory exists"""
        os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
    
    def _load_users(self) -> Dict:
        """Load users from JSON file"""
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {}
    
    def _save_users(self):
        """Save users to JSON file"""
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving users: {e}")
    
    def register_user(self, user_id: int, username: str) -> bool:
        """Register a new user or update existing user info"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.users:
            # New user - check if this is the predefined admin
            is_admin = user_id == ADMIN_USER_ID
            self.users[user_id_str] = {
                'user_id': user_id,
                'username': username,
                'is_admin': is_admin,
                'numbers_used': 0,
                'max_numbers': -1 if is_admin else 5,  # Unlimited for admin, 5 for regular users
                'phone_numbers': [],
                'created_at': datetime.now().isoformat(),
                'last_active': datetime.now().isoformat()
            }
        else:
            # Update existing user - check if admin ID changed
            if user_id == ADMIN_USER_ID:
                self.users[user_id_str]['is_admin'] = True
                self.users[user_id_str]['max_numbers'] = -1
            
            self.users[user_id_str]['username'] = username
            self.users[user_id_str]['last_active'] = datetime.now().isoformat()
        
        self._save_users()
        return True
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user data by ID"""
        user_id_str = str(user_id)
        return self.users.get(user_id_str)
    
    def set_admin(self, user_id: int) -> bool:
        """Set admin role for user"""
        user_id_str = str(user_id)
        
        if user_id_str in self.users:
            self.users[user_id_str]['is_admin'] = True
            self.users[user_id_str]['max_numbers'] = -1  # Unlimited for admins
            self._save_users()
            return True
        return False
    
    def can_generate_number(self, user_id: int) -> bool:
        """Check if user can generate more numbers"""
        user_data = self.get_user(user_id)
        if not user_data:
            return False
        
        # Admins have unlimited numbers
        if user_data['is_admin']:
            return True
        
        # Regular users have limit
        return user_data['numbers_used'] < user_data['max_numbers']
    
    def assign_number(self, user_id: int, phone_number: str) -> bool:
        """Assign a phone number to user"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.users:
            return False
        
        # Check if user can generate more numbers
        if not self.can_generate_number(user_id):
            return False
        
        # Add phone number to user's list
        number_info = {
            'phone_number': phone_number,
            'created_at': datetime.now().strftime('%H:%M:%S %d/%m/%Y'),
            'status': 'active'
        }
        
        self.users[user_id_str]['phone_numbers'].append(number_info)
        self.users[user_id_str]['numbers_used'] += 1
        self.users[user_id_str]['last_active'] = datetime.now().isoformat()
        
        self._save_users()
        return True
    
    def get_user_numbers(self, user_id: int) -> List[Dict]:
        """Get all phone numbers for a user"""
        user_data = self.get_user(user_id)
        if not user_data:
            return []
        
        return user_data.get('phone_numbers', [])
    
    def get_stats(self) -> Dict:
        """Get basic system statistics"""
        total_users = len(self.users)
        admin_count = sum(1 for user in self.users.values() if user.get('is_admin', False))
        total_numbers = sum(user.get('numbers_used', 0) for user in self.users.values())
        
        # Load SMS data for count
        sms_file = "data/sms_messages.json"
        total_sms = 0
        if os.path.exists(sms_file):
            try:
                with open(sms_file, 'r', encoding='utf-8') as f:
                    sms_data = json.load(f)
                    total_sms = sum(len(messages) for messages in sms_data.values())
            except:
                pass
        
        return {
            'total_users': total_users,
            'admin_count': admin_count,
            'total_numbers': total_numbers,
            'total_sms': total_sms
        }

# =============================================================================
# PHONE GENERATOR CLASS
# =============================================================================

class PhoneGenerator:
    def __init__(self, phone_file: str = "data/phone_numbers.json"):
        self.phone_file = phone_file
        self._ensure_data_directory()
        self.generated_numbers = self._load_generated_numbers()
        
        # Initialize real SMS API
        self._real_sms_api = None
        try:
            self._real_sms_api = RealSMSAPI()
        except:
            pass
        
        # Country codes and their patterns
        self.country_configs = {
            'US': {
                'code': '+1',
                'name': 'United States',
                'flag': '🇺🇸',
                'pattern': lambda: f"+1{random.randint(200, 999)}{random.randint(200, 999)}{random.randint(1000, 9999)}"
            },
            'UK': {
                'code': '+44',
                'name': 'United Kingdom',
                'flag': '🇬🇧',
                'pattern': lambda: f"+44{random.randint(70, 79)}{random.randint(10000000, 99999999)}"
            },
            'VN': {
                'code': '+84',
                'name': 'Vietnam',
                'flag': '🇻🇳',
                'pattern': lambda: f"+84{random.choice([3, 5, 7, 8, 9])}{random.randint(10000000, 99999999)}"
            },
            'FR': {
                'code': '+33',
                'name': 'France',
                'flag': '🇫🇷',
                'pattern': lambda: f"+33{random.randint(600000000, 799999999)}"
            },
            'DE': {
                'code': '+49',
                'name': 'Germany',
                'flag': '🇩🇪',
                'pattern': lambda: f"+49{random.randint(150, 179)}{random.randint(1000000, 9999999)}"
            },
            'CA': {
                'code': '+1',
                'name': 'Canada',
                'flag': '🇨🇦',
                'pattern': lambda: f"+1{random.randint(200, 999)}{random.randint(200, 999)}{random.randint(1000, 9999)}"
            },
            'AU': {
                'code': '+61',
                'name': 'Australia',
                'flag': '🇦🇺',
                'pattern': lambda: f"+61{random.choice([4, 5])}{random.randint(10000000, 99999999)}"
            },
            'JP': {
                'code': '+81',
                'name': 'Japan',
                'flag': '🇯🇵',
                'pattern': lambda: f"+81{random.choice([70, 80, 90])}{random.randint(10000000, 99999999)}"
            },
            'IN': {
                'code': '+91',
                'name': 'India',
                'flag': '🇮🇳',
                'pattern': lambda: f"+91{random.choice([7, 8, 9])}{random.randint(100000000, 999999999)}"
            },
            'BR': {
                'code': '+55',
                'name': 'Brazil',
                'flag': '🇧🇷',
                'pattern': lambda: f"+55{random.randint(11, 99)}{random.choice([9])}{random.randint(10000000, 99999999)}"
            }
        }
    
    def _ensure_data_directory(self):
        """Ensure data directory exists"""
        os.makedirs(os.path.dirname(self.phone_file), exist_ok=True)
    
    def _load_generated_numbers(self) -> Dict:
        """Load generated numbers from file"""
        if os.path.exists(self.phone_file):
            try:
                with open(self.phone_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {}
    
    def _save_generated_numbers(self):
        """Save generated numbers to file"""
        try:
            with open(self.phone_file, 'w', encoding='utf-8') as f:
                json.dump(self.generated_numbers, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving phone numbers: {e}")
    
    def generate_number(self, use_real_api: bool = False, service: str = 'telegram', country: str = 'russia') -> str:
        """Generate a new phone number - virtual or real"""
        if use_real_api:
            # Try to get a real number first
            try:
                # Use the real SMS API instance directly
                number_info = self._real_sms_api.get_number(service, country)
                
                if number_info:
                    phone_number = number_info['phone_number']
                    # Store in our generated numbers with real API flag
                    self.generated_numbers[phone_number] = {
                        'country_code': country.upper(),
                        'country_name': country.title(),
                        'flag': self._get_country_flag(country),
                        'generated_at': number_info['created_at'],
                        'status': 'active',
                        'type': 'real',
                        'service': service,
                        'activation_id': number_info['activation_id'],
                        'api_service': number_info['api_service']
                    }
                    self._save_generated_numbers()
                    return phone_number
            except Exception as e:
                print(f"Real API failed, falling back to virtual: {e}")
        
        # Generate virtual number
        country_code = random.choice(list(self.country_configs.keys()))
        country_config = self.country_configs[country_code]
        
        # Generate number based on country pattern
        max_attempts = 100
        for _ in range(max_attempts):
            phone_number = country_config['pattern']()
            
            # Check if number already exists
            if phone_number not in self.generated_numbers:
                # Store number info
                self.generated_numbers[phone_number] = {
                    'country_code': country_code,
                    'country_name': country_config['name'],
                    'flag': country_config['flag'],
                    'generated_at': f"{random.randint(1, 28)}/{random.randint(1, 12)}/2024 {random.randint(0, 23):02d}:{random.randint(0, 59):02d}",
                    'status': 'active',
                    'type': 'virtual'
                }
                
                self._save_generated_numbers()
                return phone_number
        
        # Fallback if all attempts failed
        fallback_number = f"+1{random.randint(2000000000, 9999999999)}"
        self.generated_numbers[fallback_number] = {
            'country_code': 'US',
            'country_name': 'United States',
            'flag': '🇺🇸',
            'generated_at': f"{random.randint(1, 28)}/{random.randint(1, 12)}/2024 {random.randint(0, 23):02d}:{random.randint(0, 59):02d}",
            'status': 'active',
            'type': 'virtual'
        }
        
        self._save_generated_numbers()
        return fallback_number
    
    def get_country_info(self, phone_number: str) -> str:
        """Get country information for a phone number"""
        if phone_number in self.generated_numbers:
            info = self.generated_numbers[phone_number]
            return f"{info['flag']} {info['country_name']}"
        
        # Fallback based on country code
        for country_code, config in self.country_configs.items():
            if phone_number.startswith(config['code']):
                return f"{config['flag']} {config['name']}"
        
        return "🌍 Unknown"
    
    def _get_country_flag(self, country: str) -> str:
        """Get flag emoji for country"""
        flags = {
            'russia': '🇷🇺', 'ukraine': '🇺🇦', 'kazakhstan': '🇰🇿',
            'china': '🇨🇳', 'philippines': '🇵🇭', 'vietnam': '🇻🇳',
            'usa': '🇺🇸', 'uk': '🇬🇧', 'poland': '🇵🇱'
        }
        return flags.get(country.lower(), '🌍')
    
    def is_real_number(self, phone_number: str) -> bool:
        """Check if phone number is from real API"""
        if phone_number in self.generated_numbers:
            return self.generated_numbers[phone_number].get('type') == 'real'
        return False

# =============================================================================
# SMS SIMULATOR CLASS
# =============================================================================

class SMSSimulator:
    def __init__(self, sms_file: str = "data/sms_messages.json"):
        self.sms_file = sms_file
        self._ensure_data_directory()
        self.sms_data = self._load_sms_data()
        
        # SMS templates for different services
        self.sms_templates = {
            'verification': [
                "Your verification code is: {code}",
                "Verification code: {code}. Do not share this code.",
                "Your OTP is {code}. Valid for 10 minutes.",
                "Code: {code}. Enter this to verify your account.",
                "Security code: {code}. Don't give this to anyone.",
                "{code} is your verification code",
                "Use {code} to verify your phone number",
                "Your login code: {code}"
            ],
            'services': [
                ('Google', 'G-{code} is your Google verification code.'),
                ('Facebook', 'Your Facebook code is {code}'),
                ('Instagram', '{code} is your Instagram code. Don\'t share it.'),
                ('WhatsApp', 'WhatsApp code: {code}. Don\'t share this code.'),
                ('Twitter', 'Your Twitter confirmation code is {code}.'),
                ('Telegram', 'Telegram code: {code}'),
                ('Discord', 'Your Discord verification code is: {code}'),
                ('TikTok', 'Your TikTok verification code is {code}'),
                ('Uber', 'Your Uber code is {code}'),
                ('PayPal', 'PayPal: Your security code is {code}'),
                ('Amazon', 'Amazon: Your OTP is {code}'),
                ('Netflix', 'Netflix verification code: {code}'),
                ('Spotify', 'Your Spotify code: {code}'),
                ('Apple', 'Your Apple ID Code is: {code}'),
                ('Microsoft', 'Microsoft account security code: {code}'),
                ('LinkedIn', 'Your LinkedIn verification code: {code}'),
                ('Snapchat', 'Snapchat code: {code}. Do not share!'),
                ('Reddit', 'Your Reddit verification code is {code}'),
                ('Twitch', 'Twitch: Your verification code is {code}'),
                ('Steam', 'Your Steam Guard access code is {code}')
            ]
        }
        
        # Start background SMS generation
        self._start_sms_generator()
    
    def _ensure_data_directory(self):
        """Ensure data directory exists"""
        os.makedirs(os.path.dirname(self.sms_file), exist_ok=True)
    
    def _load_sms_data(self) -> Dict:
        """Load SMS data from file"""
        if os.path.exists(self.sms_file):
            try:
                with open(self.sms_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {}
    
    def _save_sms_data(self):
        """Save SMS data to file"""
        try:
            with open(self.sms_file, 'w', encoding='utf-8') as f:
                json.dump(self.sms_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving SMS data: {e}")
    
    def _generate_verification_code(self) -> str:
        """Generate a random verification code"""
        return str(random.randint(100000, 999999))
    
    def _generate_sms_content(self) -> tuple:
        """Generate random SMS content and sender"""
        sms_type = random.choices(
            ['verification', 'services'],
            weights=[60, 40]  # Higher chance for verification codes
        )[0]
        
        if sms_type == 'verification':
            template = random.choice(self.sms_templates['verification'])
            code = self._generate_verification_code()
            content = template.format(code=code)
            sender = random.choice(['Verify', 'Auth', 'Security', 'Code', 'OTP'])
        
        else:  # services
            service, template = random.choice(self.sms_templates['services'])
            code = self._generate_verification_code()
            content = template.format(code=code)
            sender = service
        
        return sender, content
    
    def add_sms(self, phone_number: str, sender: str = None, content: str = None):
        """Add SMS message to a phone number"""
        if phone_number not in self.sms_data:
            self.sms_data[phone_number] = []
        
        if sender is None or content is None:
            sender, content = self._generate_sms_content()
        
        sms_message = {
            'sender': sender,
            'content': content,
            'received_at': datetime.now().strftime('%H:%M:%S %d/%m/%Y'),
            'id': l