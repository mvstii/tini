---
name: seviye4
description: Router Seviye 4 (karmaşık algoritma, yarış durumu, derin mimari) işini yüksek eforla başlatır; önce architect-planner ile uç durum planı.
argument-hint: "[görev]"
effort: high
disable-model-invocation: true
---
# SEVİYE 4: DERİN TASARIM AKIŞI

Görev: $ARGUMENTS

Bu tur yüksek eforla çalışıyor (5.5 modellerinde efor değişimi önbelleği korur; model değiştirmek korumaz, bu yüzden model değiştirme).
1. `@architect-planner` ile uç durumları, yarış koşullarını ve bileşen hiyerarşisini `SPEC.md`'ye yazdır.
2. SPEC'i oku; en riskli 2 noktayı kullanıcıya 2-3 cümleyle bildir. Geri alınamaz veya belirsiz karar varsa sor.
3. Uygula: kısa işse ana oturumda, büyükse `@implementer-sonnet`'e SPEC içeriğini istemine gömerek devret.
4. Doğrula: `@tester-healer`, sonra `/ponytail-review`. Güvenlik/eşzamanlılık diff'inde isteğe bağlı ikinci görüş: `/codex:adversarial-review` (codex plugin kuruluysa).
5. Kalıcı karar çıktıysa `MEMORY.md`'ye 1 satır yaz.
