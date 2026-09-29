# ftel_dphy_rx — Câu hỏi cho team AFE

| Mục | Nội dung |
|---|---|
| Gửi | Team AFE (analog front-end của D-PHY Rx: HS-RX, LP-RX, termination, deserializer) |
| Từ | Nhóm thiết kế D-PHY Rx digital (`ftel_dphy_rx`) |
| Ngày | 2026-09-29 |
| Căn cứ | HAS của `ftel_dphy_rx` bản nháp v0.5 (`hw/rtl/ip/ftel_dphy_rx/doc/spec.md`) §2.1 (Figure 2-1, 2-2), §4.1, §4.3, §5.2, ADR-001, ADR-004, Appendix B; MIPI D-PHY v1.1 Table 14 |

## Bối cảnh

`ftel_dphy_rx` là phần digital của D-PHY receiver. Trên đường tín hiệu nó nằm **sau** AFE và
**trước** CSI-2 Rx controller:

```
pin ──► AFE (analog) ──► ftel_dphy_rx (digital) ──PPI──► CSI-2 Rx controller
```

Ranh giới giữa AFE và phần digital (ADR-001) chưa chốt. Chúng tôi đã chấm điểm ba phương án:

| Phương án | Điểm |
|---|---|
| A: AFE giao chuỗi bit HS nối tiếp + DDR clock | 43 |
| **B: AFE giao word 1:8 chưa align byte + byte clock** | **72** |
| C: hard PHY của vendor, lên tới PPI | 52 |

Lý do nghiêng về B:
- Ở 1.5–1.8 Gb/s, phương án A đòi logic digital chạy ở tốc độ bit, không khả thi về timing.
- Phương án C làm mất phần giao thức do mình tự làm RTL.

Mỗi câu hỏi kèm **giả định đang dùng**. Thiết kế sẽ đi theo giả định đó cho tới khi có câu trả lời.
Nếu team đồng ý với giả định, chỉ cần trả lời "Đồng ý".

**Cần trả lời trước HAS v1.0** (chưa có thì chưa sinh RTL được): **A1, A2, A3**. A4 chỉ cần cho bản
R2 (deskew calibration).

## Tóm tắt

| ID | Chủ đề | Ưu tiên | Liên quan |
|---|---|---|---|
| A1 | Ranh giới AFE / digital (phương án B) và giao diện tín hiệu | **Cao** | ADR-001 |
| A2 | Bộ phát hiện clock activity cho TCLK-MISS | **Cao** | ADR-001 |
| A3 | Ngân sách thời gian bật termination | **Cao** | ADR-001 |
| A4 | Delay line cho deskew (R2) | Trung bình | ADR-001, ADR-004 |
| A5 | Độ rộng glitch tối đa ở đầu ra LP-RX | Trung bình | ADR-001 |

Có 20 yêu cầu trong HAS đang chờ các quyết định này: ADR-001 chặn 17 yêu cầu, ADR-004 chặn 3.
Ranh giới AFE / digital theo phương án B được vẽ ở HAS Figure 2-1 (data lane) và Figure 2-2 (clock lane).

## Giao diện đề xuất (HAS D-PHY §5.2)

Chiều tín hiệu nhìn từ `ftel_dphy_rx`. Hậu tố `_x` nghĩa là mỗi data lane có một tín hiệu.

| Tín hiệu | Chiều | Độ rộng | Domain | Mô tả |
|---|---|---|---|---|
| `afe_lp_dp_x`, `afe_lp_dn_x` | In | 1 mỗi tín hiệu | async | Đầu ra LP-RX của data lane x |
| `afe_cl_lp_dp`, `afe_cl_lp_dn` | In | 1 mỗi tín hiệu | async | Đầu ra LP-RX của clock lane |
| `afe_byteclk` | In | 1 | clock | DDR clock của clock lane chia 8; trở thành `rxbyteclkhs` |
| `afe_hs_word_x` | In | 8 | `afe_byteclk` | Bit đã deserialize, bit 0 nhận trước, pha byte tùy ý |
| `afe_cl_clk_active` | In | 1 | async | Bộ phát hiện clock activity cho TCLK-MISS (A2) |
| `afe_hs_en_x`, `afe_cl_hs_en` | Out | 1 mỗi tín hiệu | `core_clk` | Bật HS-RX (và deserializer) |
| `afe_term_en_x`, `afe_cl_term_en` | Out | 1 mỗi tín hiệu | `core_clk` | Bật HS termination |
| `afe_dly_tap_x` | Out | `PARA_DLY_TAP_WIDTH` | `rxbyteclkhs` | Giá trị delay line (R2, A4) |

`core_clk` là clock hệ thống 200 MHz, chu kỳ 5 ns.

---

## A1 — Ranh giới AFE / digital (phương án B)

**Câu hỏi.**
1. AFE có giao được, cho mỗi data lane, một word 8 bit đã deserialize nhưng **chưa align byte**, trên
   **một byte clock chung** (DDR clock của clock lane chia 8) không? Việc tìm sync và align byte do
   phần digital làm.
2. Bit 0 của word có phải là bit nhận trước không? Word của các lane có quan hệ timing thế nào với
   `afe_byteclk` (setup/hold tại đầu vào digital)?
3. Từ lúc `afe_hs_en_x` lên tới khi word ổn định mất bao lâu? Word trong khoảng này có thể là dữ liệu
   rác; phần digital bỏ qua mọi thứ trong thời gian THS-SETTLE.
4. `afe_byteclk` có dừng khi clock lane rời HS (vào LP hoặc ULPS) không? Khi dừng và chạy lại, clock
   có sạch (không glitch, không có xung ngắn) không?
5. Phần digital tự làm đảo cực P/N và map lane logic ↔ vật lý, cho cả đường HS lẫn đường LP. AFE có
   tự đảo hay map lại tín hiệu nào không? Nếu cả hai bên cùng đảo thì cực tính sẽ bị đảo hai lần.

**Giả định hiện tại.** Phương án B, với giao diện như bảng ở trên. `afe_byteclk` chỉ chạy khi clock
lane ở HS, và dừng/chạy lại không glitch. AFE không đảo cực và không map lane.

## A2 — Bộ phát hiện clock activity cho TCLK-MISS

**Câu hỏi.**
1. AFE có cung cấp được tín hiệu `afe_cl_clk_active` (bất đồng bộ) báo HS clock của clock lane còn
   chạy hay đã mất không? Mất bao lâu từ lúc clock dừng tới lúc tín hiệu hạ?
2. Nếu không làm được, team có chấp nhận nới yêu cầu TCLK-MISS ở tốc độ thấp không?
3. Tín hiệu này có glitch khi clock bắt đầu chạy hoặc dừng không? Phần digital đồng bộ nó vào
   `core_clk` bằng 2 flip-flop (HAS §4.1); nếu có glitch thì phải thêm bộ lọc.

**Vì sao cần.** D-PHY yêu cầu phát hiện mất HS clock trong TCLK-MISS ≤ 60 ns (Table 14). Ở 80 Mb/s,
một chu kỳ byte clock đã là 100 ns, nên phần digital chỉ nhìn `rxbyteclkhs` thì không phát hiện kịp.

**Giả định hiện tại.** AFE có bộ phát hiện này, và đầu ra không có glitch nên phần digital chỉ
cần đồng bộ, không cần lọc.

## A3 — Ngân sách thời gian bật termination

**Câu hỏi.**
1. Phần digital phát `afe_term_en_x` / `afe_cl_term_en` ngay khi phát hiện LP-00. Việc phát hiện mất
   khoảng 20 ns: 2 chu kỳ đồng bộ và 2 chu kỳ lọc glitch ở 200 MHz. AFE bật được termination trong
   phần thời gian còn lại không?
   - Data lane: TD-TERM-EN ≤ 35 ns + 4·UI, tính từ lúc đường truyền vào LP-00, nên AFE còn khoảng
     15 ns + 4·UI.
   - Clock lane: TCLK-TERM-EN ≤ 38 ns, nên AFE còn khoảng 18 ns.
2. Nếu không kịp, AFE có tự phát hiện LP-00 và tự bật termination được không? Khi đó việc chuyển
   termination nằm trong AFE, và phần digital chỉ cho phép (enable) chức năng này.

**Giả định hiện tại.** Kịp. Phần digital phát termination enable ngay khi phát hiện LP-00, không
thêm timer.

**Tham chiếu.** D-PHY v1.1 Table 14. HAS D-PHY §4.3 (design note), Appendix B.

## A4 — Delay line cho deskew (chỉ R2)

**Câu hỏi.** Delay line trên mỗi data lane có:
1. bao nhiêu tap, mỗi tap bao nhiêu ps, và tổng dải chỉnh là bao nhiêu?
2. giao diện điều khiển thế nào: bus tĩnh, và clock domain của bus? Đổi tap khi đang nhận dữ liệu thì
   có glitch không?
3. delay line nằm trên đường data, trên đường clock, hay cả hai?

**Vì sao cần.**
- Trên 1.5 Gb/s phải deskew theo D-PHY v1.2. Phần digital nhận deskew burst rồi chọn tap nằm giữa
  cửa sổ bắt đúng (ADR-004).
- Số tap quyết định `PARA_DLY_TAP_WIDTH`.
- Độ phân giải và dải chỉnh quyết định thuật toán deskew và thời gian calibrate.

**Giả định hiện tại.** Chưa có. Thuật toán mặc định: quét mọi tap trong một deskew burst, rồi chọn
tap giữa cửa sổ bắt đúng; chỉ calibrate lúc đầu (initial), không calibrate định kỳ.

## A5 — Độ rộng glitch tối đa ở đầu ra LP-RX

**Câu hỏi.**
1. Đầu ra LP-RX có thể để lọt glitch (xung ngắn) rộng tối đa bao nhiêu vào phần digital?
2. LP-RX có hysteresis không? Có thông số độ rộng xung tối thiểu nào cho đầu ra không?

**Vì sao cần.** Phần digital lọc glitch trên các trạng thái LP (`PARA_LP_FILTER_CYC`). Bộ lọc càng
dài thì càng chống glitch tốt, nhưng càng ăn vào ngân sách termination của A3.

**Giả định hiện tại.** Bộ lọc 2 chu kỳ `core_clk` (10 ns), tức glitch dài hơn 10 ns không lọt qua
LP-RX.

---

## Trả lời

| ID | Trả lời | Người trả lời | Ngày |
|---|---|---|---|
| A1 | | | |
| A2 | | | |
| A3 | | | |
| A4 | | | |
| A5 | | | |
