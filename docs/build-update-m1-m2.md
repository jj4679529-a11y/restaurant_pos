# Windows monobloklar M1 / M2: build va yangilash

M1 = PostgreSQL, server va kassa ishlaydigan monoblok.
M2 = M1 serveriga LAN orqali ulanadigan kassa. Bu Apple M1/M2 build emas.

## GitHub Actions orqali

`phase-13-two-monoblock` branchiga push bo'lganda testlardan keyin Windows build ishlaydi.
Actions → Build Windows Executables → muvaffaqiyatli run → Artifacts:

- `monoblock1-installation`: ichida `RestaurantPOS-Monoblock1.zip`.
- `monoblock2-installation`: ichida `RestaurantPOS-Monoblock2.zip`.

Har bir ichki ZIPni o'z monoblokida `C:\POSRelease` ga oching:
`C:\POSRelease\RestaurantPOS\app`, `scripts`, `version.json` bo'lishi kerak.

## Lokal build (Windows, Python 3.12 x64)

Repo papkasida PowerShell:

```powershell
git switch phase-13-two-monoblock
git pull --ff-only origin phase-13-two-monoblock
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1
```

Natija: `dist\RestaurantPOS-Monoblock1.zip` va `dist\RestaurantPOS-Monoblock2.zip`.
Lokal script faqat build qiladi. To'liq PostgreSQL va Windows tekshiruvlari GitHub Actions orqali ishlaydi.

## M1 yangilash

Kassa va adminni odatiy tarzda yoping. Saqlanmagan buyurtmani avval saqlang.
M1 paketini `C:\POSRelease` ga oching. Administrator PowerShell:

```powershell
& C:\POSRelease\RestaurantPOS\scripts\update_windows.ps1 -InstallDirectory C:\RestaurantPOS -ReleaseDirectory C:\POSRelease\RestaurantPOS -Server -Confirm:$false
```

## M2 yangilash

M2 paketini `C:\POSRelease` ga oching. Kassa va adminni yoping.
`-NoRestart` bu birinchi yangilashda eski `version.json` server rolini noto'g'ri belgilagan bo'lsa ham server/migratsiya ishga tushishini oldini oladi.
Administrator PowerShell:

```powershell
& C:\POSRelease\RestaurantPOS\scripts\update_windows.ps1 -InstallDirectory C:\RestaurantPOS -ReleaseDirectory C:\POSRelease\RestaurantPOS -NoRestart -Confirm:$false
Start-Process C:\RestaurantPOS\app\RestaurantPOS.exe
```

M2 paketidagi `version.json` da `server: false`. M2 `config\.env` ichidagi `POS_API_BASE_URL` M1 IP manziliga qarashi kerak.
Mavjud updater tekshiruvi bilan moslik uchun M2 paketida server EXE ham bor, uni ishga tushirmang.

Updater EXE va skriptlarni checksum bilan tekshiradi, oldingi fayllarni backup qiladi va config/.env, media hamda bazani saqlaydi.
Bu buyruqlar `C:\RestaurantPOS\app`, `config` va `version.json` tuzilmasidagi mavjud o'rnatish uchun.

## Bot mahsulot hisoboti

Kunlik/haftalik/oylik mahsulot hisobotida har bir variant miqdori va sotuv summasi ko'rinadi.
Bir mahsulotning bir nechta variantlari bo'lsa, mahsulot jami ham ko'rsatiladi. Oxirida umumiy summa bor.
Faqat PAID buyurtmalar hisoblanadi; summa saqlangan `OrderItem.total_price` dan olinadi (qo'shimchalar bilan), hozirgi katalog narxidan emas.
