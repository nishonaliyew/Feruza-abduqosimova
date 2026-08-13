# FERUZA ABDUQOSIMOVA BOT — GitHub + Vercel

## v2.6 — Kanal SILKA orqali qo‘shiladi

Bu versiyada kanal qo‘shish oqimi aynan quyidagicha:

1. Botni kerakli kanalga oldindan **Administrator** qilib qo‘ying.
2. Botning private chatida `/start` bosing.
3. `📢 Kanal qo‘shish` ni bosing.
4. Bot `🔗 Kanal silkasini yuboring` deb so‘raydi.
5. Ochiq kanal uchun `https://t.me/kanal_nomi`, yopiq kanal uchun `https://t.me/+XXXXXXXX` yuboring.
6. Bot kanalda o‘zi Administrator ekanini tekshiradi.
7. Kanal topilsa `Admin / Manager / Rahbar` bo‘limidan birini tanlashni so‘raydi.
8. Tanlangach kanal Supabase bazasiga yoziladi.

### Muhim: yopiq kanal

Telegram Bot API private `t.me/+...` linkni bevosita chat ID ga aylantirmaydi. Shu sabab bot kanalga admin qilingan paytdagi `my_chat_member` update orqali kanal ID sini oldindan eslab qoladi. Keyin siz tashlagan private link bilan shu kanalni qabul qiladi.

Shu sabab yangi v2.6 deploy qilingandan keyin, private kanalga bot **oldindan admin bo‘lgan bo‘lsa**, bir marta adminlikdan olib yana Administrator qilib qo‘yish kerak bo‘lishi mumkin. Keyingi qo‘shishlarda oqim odatdagidek ishlaydi.

## Guruh qo‘shish

- Botni guruhga qo‘shing.
- Guruh ichida `/qoshish` yozing.
- `Admin / Manager / Rahbar` dan birini tanlang.

## Xabar tarqatish

`/start` → `Admin / Manager / Rahbar / Hamma` → yuboriladigan xabarni jo‘nating.

Foydalanuvchi yozgan `/start`, `/qoshish`, kanal silkasi va tarqatish xabari bot tomonidan o‘chirilmaydi.

## Vercel Environment Variables

```text
BOT_TOKEN=YANGI_BOT_TOKEN
ADMIN_ID=6570315540,8831478927
SUPABASE_URL=https://PROJECT.supabase.co
SUPABASE_KEY=sb_secret_...
SETUP_SECRET=uzun_tasodifiy_secret
WEBHOOK_SECRET=boshqa_uzun_secret
```

## Webhook

Deploydan keyin bir marta:

```text
https://PROJECT.vercel.app/setup?secret=SETUP_SECRET
```

Webhook `message`, `callback_query`, `my_chat_member` update turlarini qabul qilishi kerak.

Tekshirish:

```text
https://PROJECT.vercel.app/status?secret=SETUP_SECRET
https://PROJECT.vercel.app/health
```

## GitHubga yangilash

```bash
git add .
git commit -m "Fix channel add by link"
git push
```
