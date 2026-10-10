# ftel_dphy_rx — Câu hỏi cho team AFE

| Mục | Nội dung |
|---|---|
| Gửi | Team AFE (analog front-end của D-PHY Rx: HS-RX, LP-RX, termination) |
| Từ | Nhóm thiết kế D-PHY Rx digital (`ftel_dphy_rx`) |
| Ngày | 2026-10-02; cập nhật 2026-10-03 và 2026-10-06 theo các thông báo của team AFE về ranh giới (A1); 2026-10-10: số timing theo thư viện cell 22 nm (Bối cảnh, A4, A8) |
| Căn cứ | HAS của `ftel_dphy_rx` bản nháp v0.15 (`hw/rtl/ip/ftel_dphy_rx/doc/spec.md`) §1, §2.1 (Figure 2-1, 2-2), §4.1, §4.3, §4.4, §4.6, §4.8, §5.2 (Figure 5-9), ADR-001, ADR-004, ADR-007, Appendix B; MIPI D-PHY v1.1 Table 14 (timing) và Table 27 (setup/hold của receiver) |

## Bối cảnh

`ftel_dphy_rx` là phần digital của D-PHY receiver. Trên đường tín hiệu nó nằm **sau** AFE và
**trước** CSI-2 Rx controller:

```
pin ──► AFE (analog) ──► ftel_dphy_rx (digital) ──PPI──► CSI-2 Rx controller
```

**Ranh giới: phương án A (ADR-001), theo thông báo của team AFE ngày 2026-10-06.**
- **AFE:** chỉ có HS-RX, LP-RX và termination có công tắc; không lấy mẫu, không deserialize, không
  có logic line state. Đầu ra HS của mỗi data lane là chuỗi bit chưa lấy mẫu, một dây mỗi lane. Đầu
  ra HS của clock lane là DDR clock.
- **Phần digital:**
  - lấy mẫu bit HS trên cả hai cạnh của DDR clock, deserialize 1:8, tạo byte clock `rxbyteclkhs`
    và phát hiện clock activity cho TCLK-MISS (Block No. 1);
  - tìm biên byte từ SoT leader và align byte (Block No. 4);
  - bật HS-RX và termination theo FSM của từng lane.
- **Sửa so với bản 2026-10-03.** Bản trước đọc thông báo ngày 2026-10-03 ("AFE chỉ cắt tín hiệu ở
  mức byte") thành phương án B: AFE lấy mẫu rồi cắt word 8 bit tại biên tùy ý. Cách đọc đó sai, vì
  AFE không có sampler lẫn deserializer. HAS v0.13 đã sửa ở §1 ("Who deserializes"), Table 2-1, §4.3,
  §5.2 và ADR-001.

Các phương án đã xét:

| Phương án | Điểm |
|---|---|
| **A: AFE giao chuỗi bit HS nối tiếp + DDR clock** | **43** |
| B: AFE giao word 1:8 chưa align byte + byte clock | 72 |
| C: hard PHY của vendor, lên tới PPI | 52 |

Vì sao chọn A dù điểm thấp nhất:
- **B** cần sampler và deserializer trong AFE, mà AFE không có.
- **C** thay IP này bằng macro của vendor. Đó là quyết định cấp dự án, ngoài phạm vi HAS.
- **Cái giá của A** là timing của sampler. Cửa sổ setup/hold của receiver là 0.3 UI khi tốc độ tối
  đa ≤ 1 Gb/s (300 ps ở 1 Gb/s) và 0.4 UI khi trên 1 Gb/s (267 ps ở 1500 Mb/s). Cửa sổ này phải chứa
  độ mở của flip-flop lấy mẫu và mọi chênh lệch trễ giữa clock và data, từ đầu vào AFE tới sampler.
  Clock tree tổng hợp theo flow thường dồn toàn bộ trễ của nó (45–90 ps với cell 22 nm) về một phía
  cửa sổ. Vì thế sampler và buffer DDR clock được đặt tay sát AFE, đường clock và đường data dùng
  cùng loại cell. Ước lượng ⚠️ với thư viện cell 22 nm: đạt ở corner chậm 0.72 V/125 °C, còn khoảng
  ±95 ps ở 1792 Mb/s cho chênh lệch trễ clock–data của AFE và phần digital (A8). Thư viện, body bias
  và corner sign-off chưa chốt (OPEN với physical design).

**Vì sao termination vẫn do phần digital bật.** Team AFE cho biết AFE có một mạch đơn giản phát
hiện lane ở LP hay HS để bật termination. Nếu mạch đó chỉ dựa vào LP-00 thì sẽ bật sai:
- HS request là chuỗi LP-11 → LP-01 → LP-00.
- Escape entry là chuỗi LP-11 → LP-10 → LP-00 → LP-01 → LP-00, cũng đi qua LP-01 → LP-00.
- ULPS giữ LP-00 lâu dài.

Chỉ chuỗi line state mà FSM của lane theo dõi mới phân biệt được các trường hợp này. Termination bật
chỉ theo LP-00 sẽ tải đường truyền trong escape mode và ULPS (HAS §4.3, design note). A3 hỏi chi
tiết.

Mỗi câu hỏi kèm **giả định đang dùng**. Thiết kế sẽ đi theo giả định đó cho tới khi có câu trả lời.
Nếu team đồng ý với giả định, chỉ cần trả lời "Đồng ý".

**Cần trả lời trước HAS v1.0** (chưa có thì RTL chỉ là bản nháp theo giả định, mang tag `// OPEN`,
và chưa sign-off được): **A3, A7, A8, A9, A10**. A4 chỉ cần cho bản R2 (deskew calibration). A5,
A6 và A11 không chặn cấu trúc RTL:
- A5 chỉ đổi `PARA_LP_FILTER_CYC`;
- A6 chỉ đổi giá trị lập trình của `hs_settle_cyc`;
- A11 không đổi gì nếu AFE không đảo cực, không map lane.

## Tóm tắt

| ID | Chủ đề | Ưu tiên | Liên quan | Trạng thái |
|---|---|---|---|---|
| A1 | Ranh giới AFE / digital | — | ADR-001 | Đã trả lời 2026-10-06: phương án A |
| A2 | Bộ phát hiện clock activity cho TCLK-MISS | — | ADR-001 | Bỏ 2026-10-06: nay nằm trong Block No. 1 |
| A3 | Termination: ai bật, và ngân sách thời gian | **Cao** | ADR-001 | Chờ |
| A4 | Delay line cho deskew (R2) | Trung bình | ADR-001, ADR-004 | Chờ |
| A5 | Độ rộng glitch tối đa ở đầu ra LP-RX | Trung bình | ADR-001 | Chờ |
| A6 | Đầu ra HS-RX của data lane trong THS-PREPARE | Trung bình | ADR-001, ADR-007 | Chờ; độ trễ word Λ không còn hỏi |
| A7 | Tốc độ tối đa của HS-RX | **Cao** | ADR-001, K1 | Chờ (mới) |
| A8 | Chênh lệch trễ clock–data và duty cycle của DDR clock | **Cao** | ADR-001 | Chờ (mới) |
| A9 | Đầu ra HS-RX khi tắt, khi khởi động và khi dừng | **Cao** | ADR-001 | Chờ (mới) |
| A10 | Một hay hai enable cho mỗi lane | **Cao** | ADR-001 | Chờ (mới) |
| A11 | Đảo cực P/N và map lane trong AFE | Trung bình | ADR-001 | Chờ (trước là A1 ý 5) |

Trong HAS v0.13, 22 yêu cầu chờ ADR-001, trong đó 4 yêu cầu chờ cả ADR-004 (delay line, A4). Hai
trong 22 yêu cầu chỉ chờ physical design (corner sign-off, đặt tay sampler), nên 20 yêu cầu chờ
team AFE. Độ trễ word Λ của ADR-007 nay do Block No. 1 quyết định, không còn chờ team AFE.
Ranh giới AFE / digital theo phương án A được vẽ ở HAS Figure 2-1 (data lane) và Figure 2-2 (clock lane).

## Giao diện đề xuất (HAS D-PHY §5.2)

Chiều tín hiệu nhìn từ `ftel_dphy_rx`. Hậu tố `_x` nghĩa là mỗi data lane có một tín hiệu.

| Tín hiệu | Chiều | Độ rộng | Domain | Mô tả |
|---|---|---|---|---|
| `afe_lp_dp_x`, `afe_lp_dn_x` | In | 1 mỗi tín hiệu | async | Đầu ra LP-RX của data lane x |
| `afe_cl_lp_dp`, `afe_cl_lp_dn` | In | 1 mỗi tín hiệu | async | Đầu ra LP-RX của clock lane |
| `afe_cl_hs_clk` | In | 1 | clock | Đầu ra HS-RX của clock lane: DDR clock (line rate / 2), mức CMOS; Low khi HS-RX tắt (A9) |
| `afe_hs_bit_x` | In | 1 | `afe_cl_hs_clk`, cả hai cạnh | Đầu ra HS-RX của data lane x: chuỗi bit mức CMOS, chưa lấy mẫu. Tx đặt mỗi cạnh DDR clock vào giữa một bit. Chênh lệch trễ clock–data và duty cycle nằm trong ngân sách của A8 |
| `afe_hs_en_x`, `afe_cl_hs_en` | Out | 1 mỗi tín hiệu | `core_clk` | Bật HS-RX |
| `afe_term_en_x`, `afe_cl_term_en` | Out | 1 mỗi tín hiệu | `core_clk` | Bật HS termination. AFE chỉ có một enable mỗi lane thì dùng tín hiệu này (A10) |
| `afe_dly_tap_x` | Out | `PARA_DLY_TAP_WIDTH` | `rxbyteclkhs` | Giá trị delay line (R2), chỉ khi AFE có delay line (A4) |

`core_clk` là clock hệ thống 200 MHz, chu kỳ 5 ns.

---

## A1 — Ranh giới AFE / digital (đã trả lời)

- **2026-10-03.** Team AFE thông báo "AFE chỉ cắt tín hiệu ở mức byte". Bản trước của file này đọc
  thành phương án B.
- **2026-10-06.** Team AFE cho biết AFE chỉ có HS-RX, LP-RX và termination, cùng một mạch đơn giản
  phát hiện lane ở LP hay HS để bật termination. Đây là phương án A, và thay cho cách đọc ngày
  2026-10-03.

Các ý còn mở của A1 bản trước:
- **Ý 1** (byte clock chung cho mọi lane): không còn hỏi. Phần digital tự tạo byte clock từ DDR clock
  của clock lane, nên mọi lane dùng chung.
- **Ý 2** (thứ tự bit, timing word tại đầu vào digital): thay bằng A8.
- **Ý 3** (thời gian từ enable tới word ổn định): thay bằng A6 và A9.
- **Ý 4** (byte clock dừng và chạy lại, glitch khi `afe_cl_hs_en` đổi): thay bằng A9.
- **Ý 5** (đảo cực, map lane): chuyển thành A11.

## A2 — Bộ phát hiện clock activity cho TCLK-MISS (bỏ ngày 2026-10-06)

AFE không cần cung cấp `afe_cl_clk_active` nữa. Phần digital tự phát hiện trong Block No. 1 (HAS
§4.3):
- Hai toggle flip-flop chạy ở cạnh lên của DDR clock: một cái đổi ở mỗi cạnh (line rate / 4), một
  cái đổi ở mỗi cạnh thứ tư (line rate / 16). Mỗi cái qua bộ đồng bộ 2 flip-flop vào `core_clk`.
- Clock bị coi là mất khi không toggle nào đổi trong 8 chu kỳ `core_clk` (40 ns). `cl_rxclkactivehs`
  hạ chậm nhất 60 ns sau cạnh cuối của DDR clock, tức trong TCLK-MISS ≤ 60 ns (HAS v0.14) ⚠️.

Điều kiện còn lại từ phía AFE nằm ở A9: DDR clock ở mức Low khi HS-RX tắt.

## A3 — Termination: ai bật, và ngân sách thời gian

**Câu hỏi.**
1. Mạch phát hiện LP/HS của AFE dựa vào tín hiệu nào, ví dụ đầu ra LP-RX hay mức common mode? Mạch
   này có đầu vào enable từ phần digital không?
2. Phần digital phát `afe_term_en_x` / `afe_cl_term_en` bằng thanh ghi của trạng thái FSM vào khi
   thấy LP-00 sau HS request, không thêm timer. Từ lúc đầu ra LP-RX đổi tới lúc enable lên mất
   25–30 ns:
   - phát hiện LP-00 mất 20–25 ns tùy pha lấy mẫu: 2 chu kỳ đồng bộ và bộ lọc glitch 2 chu kỳ ở
     200 MHz;
   - thanh ghi của FSM thêm 1 chu kỳ;
   - thêm 5 ns nữa nếu flip-flop đồng bộ đầu tiên resolve trễ một chu kỳ.

   AFE bật được termination trong phần thời gian còn lại không?
   - Data lane: TD-TERM-EN ≤ 35 ns + 4·UI, tính từ lúc Dn qua VIL,MAX. AFE còn 5–10 ns + 4·UI cho độ
     trễ của LP-RX và việc bật termination.
   - Clock lane: TCLK-TERM-EN ≤ 38 ns. AFE còn 8–13 ns.
3. Nếu không kịp: AFE có tự bật termination khi thấy LP-00 được không, với điều kiện phần digital
   cho phép (arm) trước? Phần digital chỉ arm khi FSM đã thấy HS request (LP-11 → LP-01). Escape
   entry và ULPS không arm, nên termination không bật sai.

**Vì sao cần.** Termination chỉ được bật trong HS. Chỉ FSM của lane phân biệt được HS request với
escape entry và ULPS (mục Bối cảnh). Mặt khác, ngân sách thời gian của AFE nhỏ hơn 10 ns.

**Giả định hiện tại.**
- AFE bật termination đúng theo `afe_term_en_x` / `afe_cl_term_en`, và kịp trong phần thời gian còn
  lại.
- Mạch phát hiện LP/HS của AFE, nếu có, không tự bật termination khi không có enable của phần digital.

**Sửa so với bản HAS v0.11.** Bản đó ghi phần digital mất khoảng 20 ns, và AFE còn khoảng
15 ns + 4·UI (data lane) và 18 ns (clock lane). Con số đó bỏ sót độ trễ lấy mẫu và chu kỳ thanh ghi
của FSM.

**Tham chiếu.** D-PHY v1.1 Table 14. HAS D-PHY §4.3 (design note), Appendix B.

## A4 — Delay line cho deskew (chỉ R2)

Theo thông báo ngày 2026-10-06, AFE không có delay line. Deskew calibration của R2 (trên 1.5 Gb/s,
theo D-PHY v1.2) cần một delay line trước sampler của mỗi data lane.

**Câu hỏi.**
1. Team AFE có thêm được delay line trên đầu ra HS-RX của mỗi data lane cho R2 không? Nếu có:
   - bao nhiêu tap, mỗi tap bao nhiêu ps, tổng dải chỉnh là bao nhiêu?
   - giao diện điều khiển thế nào: bus tĩnh, và clock domain của bus? Đổi tap khi đang nhận dữ liệu
     thì có glitch không?
   - delay line nằm trên đường data, trên đường clock, hay cả hai?
2. Nếu không: delay line phải làm bằng cell chuẩn trong phần digital. Mỗi bước là một buffer, khoảng
   15–30 ps tùy corner với cell 22 nm, so với UI 558 ps ở 1792 Mb/s. Dải chỉnh và độ phân giải vì thế
   trôi khoảng 2 lần giữa các corner ⚠️ (HAS §4.8). Team có ý kiến không?

**Vì sao cần.**
- Phần digital nhận deskew burst rồi chọn tap nằm giữa cửa sổ bắt đúng (ADR-004).
- Số tap quyết định `PARA_DLY_TAP_WIDTH`.
- Độ phân giải và dải chỉnh quyết định thuật toán deskew và thời gian calibrate.

**Giả định hiện tại.** R1 không dùng delay line: `PARA_DESKEW_EN` = 0, `afe_dly_tap_x` giữ giá trị
reset. R2 chờ câu trả lời này. Thuật toán mặc định: quét mọi tap trong một deskew burst, rồi chọn
tap giữa cửa sổ bắt đúng; chỉ calibrate lúc đầu (initial), không calibrate định kỳ.

## A5 — Độ rộng glitch tối đa ở đầu ra LP-RX

**Câu hỏi.**
1. Đầu ra LP-RX có thể để lọt glitch (xung ngắn) rộng tối đa bao nhiêu vào phần digital?
2. LP-RX có hysteresis không? Sơ đồ LP-RX tham khảo mà nhóm digital nhận được ngày 2026-10-05 dùng
   hai comparator (ngưỡng VIH và VIL) và một SR latch. Thiết kế của team có như vậy không? Có thông
   số độ rộng xung tối thiểu nào cho đầu ra không?

**Vì sao cần.** Phần digital lọc glitch trên các trạng thái LP (`PARA_LP_FILTER_CYC`). Bộ lọc càng
dài thì càng chống glitch tốt, nhưng càng ăn vào ngân sách termination của A3.

**Giả định hiện tại.** Bộ lọc 2 chu kỳ `core_clk` (10 ns), tức glitch dài hơn 10 ns không lọt qua
LP-RX.

## A6 — Đầu ra HS-RX của data lane trong THS-PREPARE

**Đổi ngày 2026-10-06.** Độ trễ word Λ nay do deserializer của Block No. 1 đặt: Λ = 2, xác nhận khi
có RTL của block. Vì thế bản này không còn hỏi Λ. Trễ của HS-RX nằm trong Λ, nhưng nhỏ so với một
byte clock (4.46 ns ở 1792 Mb/s) ⚠️.

**Câu hỏi.**
1. Trong THS-PREPARE (đường truyền chuyển từ LP-00 sang HS-0, termination vừa bật), `afe_hs_bit_x`
   mang gì: luôn 0, luôn 1, hay giá trị bất kỳ?
2. Tính từ đầu LP-00, sau bao lâu thì đầu ra phản ánh đúng HS-0?
3. Trễ của HS-RX, từ chân tới đầu ra, là bao nhiêu?

**Vì sao cần.**
- Từ HAS v0.9, phần digital bắt đầu tìm sync khi hết THS-SETTLE và bỏ qua mọi word đến trước đó
  (§4.6, ADR-007). Điểm bắt đầu này do `hs_settle_cyc` đặt.
- Theo D-PHY Table 14, phần digital chấp nhận rác tới THS-SETTLE,min (85 ns + 6·UI tính từ đầu
  THS-PREPARE). Nếu rác kéo dài hơn mốc này, `hs_settle_cyc` vẫn chỉnh được trong một khoảng, nhưng
  cần biết trước.

**Giả định hiện tại.** Đầu ra có thể là rác, kể cả luôn là 1, cho tới THS-SETTLE,min. Trễ của HS-RX
dưới 1 ns ⚠️.

## A7 — Tốc độ tối đa của HS-RX (mới)

**Câu hỏi.**
1. HS-RX của data lane và của clock lane chạy tới tốc độ nào, ở mọi corner? Sơ đồ tham khảo ghi
   khối HS ở 80–1000 Mb/s.
2. Theo đó, receiver theo cửa sổ setup/hold 0.3 UI (tốc độ tối đa ≤ 1 Gb/s) hay 0.4 UI (trên
   1 Gb/s) của D-PHY Table 27?

**Vì sao cần.**
- HAS đề xuất R1 ở 80–1500 Mb/s và R2 ở 80–1792 Mb/s (OPEN K1, do CSI team chốt). Nếu HS-RX chỉ
  tới 1 Gb/s thì tốc độ của R1 phải xem lại. Đó là quyết định của CSI team và dự án, không phải của
  nhóm digital.
- Tốc độ tối đa quyết định cửa sổ lấy mẫu, nên quyết định cả ngân sách timing của sampler (A8).

**Giả định hiện tại.** HS-RX chạy tới 1500 Mb/s ⚠️.

## A8 — Chênh lệch trễ clock–data và duty cycle của DDR clock (mới)

**Câu hỏi.**
1. Tại đầu ra AFE, trễ của HS-RX clock lane và trễ của HS-RX mỗi data lane chênh nhau bao nhiêu? Cần
   min/max qua process, điện áp và nhiệt độ. Các HS-RX có tương quan với nhau không (cùng mạch, cùng
   layout)?
2. Duty cycle của `afe_cl_hs_clk` lệch tối đa bao nhiêu so với 50%? Sampler dùng cả hai cạnh, nên
   lỗi duty cycle ăn trực tiếp vào cửa sổ.
3. Đầu ra HS-RX nằm ở đâu trên die? Sampler sẽ được đặt tay ngay cạnh đó.

**Vì sao cần.** Cửa sổ setup/hold (A7) phải chứa độ mở của sampler và mọi chênh lệch trễ clock–data,
từ đầu vào AFE tới sampler. Ước lượng của nhóm digital, với thư viện cell 22 nm và sampler đặt tay ⚠️:
- Ở corner chậm (0.72 V, 125 °C) còn khoảng ±115 ps ở 1500 Mb/s, ±95 ps ở 1792 Mb/s và ±130 ps ở
  1 Gb/s cho AFE và phần digital cộng lại, kể cả lỗi duty cycle.
- Độ mở của flip-flop lấy mẫu khoảng 20 ps ở corner nhanh (0.88 V, −40 °C) và 35 ps ở corner chậm.
- Thư viện, body bias và corner sign-off chưa chốt. Câu này đang hỏi physical design.

**Giả định hiện tại.** Chưa chia ngân sách giữa AFE và phần digital: HAS chỉ ghi tổng. Việc chia sẽ
chốt cùng team AFE và physical design, sau khi có số của AFE.

## A9 — Đầu ra HS-RX khi tắt, khi khởi động và khi dừng (mới)

**Câu hỏi.**
1. Khi HS-RX tắt, `afe_cl_hs_clk` và `afe_hs_bit_x` ở mức nào? Trong sơ đồ HS-RX tham khảo, output
   MUX kéo đầu ra về GND khi `ven_hr` ở mức thấp.
2. Từ lúc enable lên tới khi DDR clock chạy đúng mất bao lâu?
3. Trong lúc khởi động và lúc dừng, DDR clock có xung ngắn (runt) không, và độ rộng tối thiểu bao
   nhiêu? Lúc dừng gồm: clock lane vào LP hay ULPS, hoặc phần mềm tắt clock lane khiến
   `afe_cl_hs_en` hạ giữa chừng.

**Vì sao cần.**
- DDR clock clock trực tiếp sampler, shift register, bộ chia 4 và toggle flip-flop của phần digital.
- Byte clock chỉ qua clock gate khi clock lane ở CL_HS_CLK. Enable của gate đi qua một reset
  synchronizer trong DDR clock: xoá ngay, set ở cạnh thứ hai. Vì thế xung ngắn lúc khởi động và lúc
  dừng không tới `rxbyteclkhs`.
- Xung ngắn vẫn có thể làm flip-flop metastable. Phần digital chịu được miễn là clock sạch trước khi
  gate mở (HAS §4.3) ⚠️.
- Mức Low khi tắt giúp bộ phát hiện clock activity (A2) thấy clock đã dừng.

**Giả định hiện tại.**
- `afe_cl_hs_clk` ở mức Low khi HS-RX tắt (HAS Table 5-2).
- Xung lúc khởi động và lúc dừng được bỏ qua.
- Clock sạch từ khi FSM của clock lane vào CL_HS_CLK.

## A10 — Một hay hai enable cho mỗi lane (mới)

**Câu hỏi.**
1. Sơ đồ HS-RX tham khảo dùng một chân `ven_hr` cho cả termination, power switch của HS-RX và output
   MUX. HS-RX của team có một enable hay hai (HS-RX riêng, termination riêng)?
2. Nếu chỉ có một: từ lúc `ven_hr` lên tới khi đầu ra HS-RX đúng mất bao lâu? Power switch của sơ đồ
   tham khảo là một chuỗi inverter lớn dần.

**Vì sao cần.**
- Phần digital có hai enable mỗi lane. `afe_term_en_x` lên ở DL_HS_PRPR, khi thấy LP-00.
  `afe_hs_en_x` lên ở DL_HS_TERM, 30–35 ns sau.
- Nếu AFE chỉ có một enable, nó dùng `afe_term_en_x` (HAS Table 5-2), nên HS-RX bật sớm hơn 30–35 ns.
  Đầu ra trước THS-SETTLE,min đằng nào cũng bị bỏ qua (A6), nên chức năng không đổi.
- Thời gian khởi động của HS-RX vẫn cần biết, để kiểm rằng đầu ra đúng trước khi phần digital bắt đầu
  tìm sync.

**Giả định hiện tại.** AFE có hai enable. Nếu chỉ có một thì nối với `afe_term_en_x`.

## A11 — Đảo cực P/N và map lane trong AFE (trước là A1 ý 5)

**Câu hỏi.** Phần digital tự làm đảo cực P/N và map lane logic ↔ vật lý, cho cả đường HS lẫn đường
LP. AFE có tự đảo hay map lại tín hiệu nào không? Nếu cả hai bên cùng đảo thì cực tính sẽ bị đảo hai
lần.

**Giả định hiện tại.** AFE không đảo cực và không map lane.

---

## Trả lời

| ID | Trả lời | Người trả lời | Ngày |
|---|---|---|---|
| A1 | Một phần: "AFE chỉ cắt tín hiệu ở mức byte". Bản trước của file này đọc thành phương án B; câu trả lời ngày 2026-10-06 thay cách đọc đó | Team AFE | 2026-10-03 |
| A1 | AFE chỉ có HS-RX, LP-RX và termination, cùng một mạch đơn giản phát hiện lane ở LP hay HS để bật termination; không có sampler, không deserialize: phương án A | Team AFE | 2026-10-06 |
| A2 | Không cần trả lời: clock activity nay nằm trong Block No. 1 (HAS v0.13 §4.3) | — | 2026-10-06 |
| A3 | | | |
| A4 | | | |
| A5 | | | |
| A6 | | | |
| A7 | | | |
| A8 | | | |
| A9 | | | |
| A10 | | | |
| A11 | | | |
