# PROJE KALICI HAFIZASI (MEMORY CONSOLIDATION)
Bu dosya oturumlar arasında öğrenilen mimari kararları, çözülen kritik bug'ları ve proje kurallarını tutar.

## Mimari Kararlar
- Proje Adı: `tini` (aegis-hybrid-harness koşum takımı ile kuruldu: 2026-10-29)
- Dil/framework: (ilk koddan sonra buraya yazın)

## Öğrenilen Dersler & Yasaklı Desenler
- KURAL: Bash'te `ls a b` iki desenden biri eşleşmezse hata kodu döner; var olma testi için `find` veya `compgen -G` kullan.
- KURAL: Windows'ta npm global araçlarını `.cmd` uzantısıyla çağır (`gemini.cmd`, `codex.cmd`); PowerShell'de `npm.cmd` kullan.
- KURAL: Düzenlenen `.sh` dosyalarında CRLF kontrolü yap (`git ls-files --eol`); CRLF bash'i bozar.
- KURAL: Alt ajan raporları doğrulanmadan uygulanmaz; iddiayı komutla kontrol et.
- KURAL: Ajan tanımını değiştirdikten sonra yeni oturumda dene.
- KURAL (guard): Bir kanca işlemi engellerse dur; hangi kuralın neyi engellediğini kullanıcıya bildir. Başka araçla veya yazımı değiştirerek aşma.

## Aşama Durumu
- Kurulum yapıldı; açık iş yok.
