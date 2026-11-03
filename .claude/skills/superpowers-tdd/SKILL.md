---
name: superpowers-tdd
description: Yeni davranış veya hata düzeltmesinde zorunlu Red→Green→Refactor döngüsü ve 4 aşamalı kök neden debug metodolojisi (Superpowers'tan uyarlandı).
---
# TDD VE KÖK NEDEN DEBUG

## Red → Green → Refactor
1. **Red:** Önce başarısız test yaz; çalıştır ve **doğru nedenle** kırıldığını gör (derleme hatası değil, beklenen assertion).
2. **Green:** Testi geçiren en küçük kodu yaz.
3. **Refactor:** Testler yeşilken sadeleştir; her adımda yeniden çalıştır.
- Testi geçirmek için assertion silme/zayıflatma, `Skip`/`Ignore` ekleme YASAK.
- Saf stil/format/dokümantasyon işlerinde TDD gerekmez.
- Test koşumu ve log süzme: `@tester-healer`.

## Kök neden debug (4 aşama; tahminle yama yapma)
1. **Yeniden üret:** Hatayı tekrarlanabilir bir komut/test haline getir.
2. **Daralt:** Katman/commit/girdi ikiye bölerek hatanın kaynağını bul (`git bisect`, log, minimal örnek).
3. **Hipotez:** Tek bir kök neden hipotezi kur; kanıtla veya çürüt (yazdırma/test ile).
4. **Düzelt + kilitle:** Kök nedeni düzelt, adım 1'in testini kalıcı regresyon testi olarak bırak. Ders çıkarsa CLAUDE.md'deki ders kuralını uygula (zorlanabiliyorsa kanca/test, değilse MEMORY.md).
Aynı hata 2 yamadan sonra sürüyorsa dur: varsayımlarını baştan gözden geçir.
