# FERUZA ABDUQOSIMOVA BOT — GitHub + Vercel

Bu versiya Vercel uchun qayta tuzilgan:

- `run_polling()` o‘rniga **Telegram Webhook** ishlaydi.
- `channels.json` o‘rniga **Supabase** doimiy bazasi ishlaydi.
- Guruh faqat **guruh ichida `/qoshish`** orqali qo‘shiladi.
- Kanal **bot shaxsiy chatida `📢 Kanal qo‘shish` → botni kanalga Administrator qilish** orqali avtomatik aniqlanadi. Public ham, yopiq/private kanal ham ishlaydi.
- Bot chatni clean saqlaydi: `/start` va tarqatish uchun yuborilgan admin xabari ishlatilgach o‘chiriladi.
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

**Muhim:** 2.2.0 versiyada yopiq kanalni avtomatik aniqlash uchun webhook `my_chat_member` update turini ham qabul qiladi. Yangi kod deploy bo‘lgach `/setup` URLini **yana bir marta** oching.

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

1. Botning shaxsiy chatida `/start` bosing.
2. `📢 Kanal qo‘shish` ni bosing.
3. Telegram kanal sozlamasiga o‘ting va shu botni kanalga **Administrator** qilib qo‘shing.
4. Bot kanalni avtomatik aniqlaydi va private chatdagi panelda kanal nomini ko‘rsatadi.
5. `Admin / Manager / Rahbar` bo‘limini tanlang.

> Kanal linkini yuborish shart emas. Shu sabab public kanal ham, `t.me/+...` yopiq/private kanal ham qo‘shiladi.
> Agar bot kanalga oldindan admin qilib qo‘yilgan bo‘lsa, `📢 Kanal qo‘shish`ni bosgandan keyin botni kanaldan olib qayta Administrator qilib qo‘shing — yangi `my_chat_member` hodisasi kelishi kerak.

### Xabar tarqatish

`/start` → `Admin / Manager / Rahbar / Hamma` → kerakli xabarni yuboring. Bot xabarni tarqatib bo‘lgach admin yuborgan original xabarni clean qiladi va panelga qaytadi.

## Fayllar

- `index.py` — FastAPI + Telegram webhook bot
- `supabase.sql` — baza
- `requirements.txt` — Python paketlari
- `.env.example` — ENV namuna
- `.gitignore` — secret/fayllarni Git’dan himoyalaydi
- `.python-version` — Python 3.12
