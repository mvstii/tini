---
name: aegis-handoff
description: Oturum sonu/`/clear` öncesi kararları, açık işleri ve değişen dosyaları ≤40 satırlık .aegis/STATE.md'ye yazar.
disable-model-invocation: true
---
# AEGIS HANDOFF

`.aegis/STATE.md` dosyasını (yoksa oluştur) baştan yaz. En fazla 40 satır; ham log, kod veya dosya içeriği yazma.

1. Değişen dosyalar: `git status --short` çıktısından yol listesi (en çok 15; fazlası "+N dosya").
2. Bölümler, sırayla:
   - `## Hedef`: aktif işin 1-2 satırı (`SPEC.md` "## Hedef" ile tutarlı).
   - `## Kararlar`: alınan mimari/tasarım kararları, her biri "karar, gerekçe" tek satır.
   - `## Açık işler`: yapılmamış veya doğrulanmamış adımlar, madde başına bir satır.
   - `## Dosyalar`: yukarıdaki liste.
   - `## Riskler`: bilinen kırık nokta veya başarısız deneme.
3. Kalıcı kural çıktıysa yalnızca onu `MEMORY.md`'ye 1 satır ekle; STATE.md oturum devir notudur, kalıcı hafıza değil.
4. Bitince kullanıcıya dosya yolunu ve satır sayısını söyle; iş bittiyse `/clear`, sürüyorsa `/compact` öner.

`SessionStart` kancası bu dosyanın başlığını sonraki oturumda devir notuna ekler.
