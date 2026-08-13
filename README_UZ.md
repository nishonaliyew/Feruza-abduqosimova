# FERUZA ABDUQOSIMOVA BOT — GitHub + Vercel

Bu versiya Vercel uchun qayta tuzilgan:

- `run_polling()` o‘rniga **Telegram Webhook** ishlaydi.
- `channels.json` o‘rniga **Supabase** doimiy bazasi ishlaydi.
- Guruh faqat **guruh ichida `/qoshish`** orqali qo‘shiladi.
- Kanal faqat **bot shaxsiy chatida `📢 Kanal qo‘shish` → kanal linkini yuborish** orqali qo‘shiladi.
- Bot chatni clean saqlaydi: `/start`, kanal linki va tarqatish uchun yuborilgan admin xabari ishlatilgach o‘chiriladi.
- Shaxsiy chatda ko‘p xabar tashlamaydi: asosiy boshqaruv oynasi imkon qadar **bitta panel xabarini edit qilib** ishlaydi.
- Guruhda `/qoshish` komandasi va tanlash oynasi ish tugagach o‘chadi.

## 0. MUHIM — bot tokenini almashtiring

Eski loyihadagi Telegram bot tokeni `bot.py` ichida ochiq yozilgan edi. **BotFather orqali eski tokenni revoke qilib, yangi token oling.** Eski tokenni GitHub yoki Vercelga qo‘ymang.

## 1. Supabase tayyorlash

1. Supabase’da project oching.
2. `supabase.sql` faylini SQL Editor’da ochib **RUN** qiling.
3. Quyidagilarni oling:
   - `SUPABASE_URL`
   - server uchun `sb_secret_...` **Secret key** (yoki eski `service_role`).

## 2. GitHubga push

```bash
git init
git add .
git commit -m "Rahbar bot Vercel webhook"
git branch -M master
git remote add origin https://github.com/USERNAME/REPO.git
git push -u origin master
```

`.env` GitHubga chiqmaydi.

## 3. Vercel

GitHub repo’ni Vercelga Import qiling. FastAPI `index.py` entrypointini Vercel avtomatik aniqlaydi.

Environment Variables:

```text
BOT_TOKEN=YANGI_BOT_TOKEN
ADMIN_ID=8831478927
SUPABASE_URL=https://PROJECT.supabase.co
SUPABASE_KEY=sb_secret_...
SETUP_SECRET=uzun_tasodifiy_secret
WEBHOOK_SECRET=boshqa_uzun_secret
```

`WEBHOOK_SECRET` uchun faqat `A-Z a-z 0-9 _ -` ishlating.

## 4. Webhookni ulash

Deploy tugagach bir marta browserda:

```text
https://PROJECT.vercel.app/setup?secret=SETUP_SECRET
```

Tekshirish:

```text
https://PROJECT.vercel.app/status?secret=SETUP_SECRET
https://PROJECT.vercel.app/health
```

`/health` da `missing_env: []` bo‘lsa ENV to‘g‘ri.

## 5. Ishlatish tartibi

### Guruh qo‘shish

1. Botni guruhga qo‘shing.
2. Botga xabarlarni o‘chirish imkonini beradigan admin huquqi berilsa, clean rejim to‘liq ishlaydi.
3. Guruh administratori guruh ichida `/qoshish` yozadi.
4. `Admin / Manager / Rahbar` dan birini tanlaydi.
5. `/qoshish` va tanlash xabari chatdan o‘chadi; guruh bazaga yoziladi.

### Kanal qo‘shish

1. Botni kanalga Administrator qiling.
2. Botning shaxsiy chatida `/start` bosing.
3. `📢 Kanal qo‘shish` ni bosing.
4. `https://t.me/kanal_nomi` yoki `@kanal_nomi` yuboring.
5. `Admin / Manager / Rahbar` bo‘limini tanlang.

> Public `t.me/username` kanal linklari to‘g‘ridan-to‘g‘ri ishlaydi. Private invite link (`t.me/+...`) Telegram Bot API orqali username kabi resolve qilinmaydi.

### Xabar tarqatish

`/start` → `Admin / Manager / Rahbar / Hamma` → kerakli xabarni yuboring. Bot xabarni tarqatib bo‘lgach admin yuborgan original xabarni clean qiladi va panelga qaytadi.

## Fayllar

- `index.py` — FastAPI + Telegram webhook bot
- `supabase.sql` — baza
- `requirements.txt` — Python paketlari
- `.env.example` — ENV namuna
- `.gitignore` — secret/fayllarni Git’dan himoyalaydi
- `.python-version` — Python 3.12
