# Nháp: nội dung gửi team CSI sau HAS D-PHY v0.9, v0.11, v0.13, v0.14 và v0.15 (để duyệt, chưa gửi)

File nội bộ. Phần 1 dành cho người duyệt và không gửi đi. Phần 2 là bản nháp viết cho team CSI-2 Rx
controller, theo đúng khuôn của `questions_csi_team.md`. Duyệt xong thì chép các mục được chọn vào
`questions_csi_team.md`, rồi xóa file này.

---

## Phần 1 — Ghi chú cho người duyệt (không gửi)

**HAS v0.9 chạm tới team CSI ở đâu.** PPI không đổi gì. Điểm bắt đầu tìm sync (ADR-007, phương án D)
là việc bên trong D-PHY; thời điểm `rxactivehs_x`, `rxsynchs_x`, `rxvalidhs_x` và `errsotsynchs_x`
vẫn như v0.8. Có hai chỗ team CSI có thể quan tâm:

| # | Nội dung | Đề xuất | Lý do |
|---|---|---|---|
| 1 | **Leader hỏng** (2 bit lỗi trở lên) thường dẫn tới khóa sai trong payload, không phải `errsotsynchs_x` như HAS-CSI Figure 4-2 vẽ | **Gửi** (mục ADR-007 ở Phần 2) | Đây là sắc thái của hợp đồng PPI (C8). Hành vi này có ở mọi D-PHY Rx so leader cho phép sai 1 bit, không do v0.9 gây ra. Báo sớm để team quyết định có cần đổi gì không |
| 2 | **Bảng `hs_settle_cyc` đổi** (Appendix B): 80 Mb/s 39 → 70, 1500 Mb/s 20 → 19 (với Λ = 2) | **Gửi dạng ghi chú** dưới K3, không thành câu hỏi | Chỉ liên quan nếu driver của controller lập trình timing D-PHY (K3 chưa chốt). Không thêm trường nào |
| 3 | PPI không đổi ở v0.9 | **Gửi một dòng** ở phần cập nhật đầu file | Giúp team biết không cần xem lại waveform |
| 4 | Finding F-003 (`eot_skip_bytes` có thể thiếu độ trễ đường dữ liệu), mô hình ADR-007, ma trận chấm điểm | **Không gửi** | Việc nội bộ, chưa có kết luận (F-003 còn chờ mô hình EoT) |

**HAS v0.11 chạm tới team CSI ở đâu.** v0.11 đổi PPI ở ba điểm, và hai điểm cần team CSI trả lời theo
lựa chọn của bạn ngày 2026-10-02:

| # | Nội dung | Đề xuất | Lý do |
|---|---|---|---|
| 5 | **S12, clock sau burst cuối.** Khi clock lane rời HS (ULPS, dừng stream), đuôi burst cuối nằm lại trong delay line tới khi clock chạy lại. Tx được hỏi TCLK-POST ≥ 288·UI; controller có Lane Management chạy trên `rxbyteclkhs`, nên cũng cần clock sau byte cuối | **Gửi** (mục S12 ở Phần 2) | Bạn chọn "Hỏi Tx và CSI". Con số của controller cộng vào con số hỏi Tx |
| 6 | **Burst kết thúc trước khi lock** (ví dụ short packet trên 4 lane, leader hỏng): D-PHY nay phát một xung `errsotsynchs_x` ở chu kỳ cuối của `rxactivehs_x` | **Gửi** (câu 3 của mục ADR-007) | Bạn chọn "Phát khi EoT". Theo Burst FSM của HAS-CSI, burst vẫn bị hủy như trước, chỉ đổi nguyên nhân abort từ "unarmed" sang errsotsynchs |
| 7 | **`forcerxmode_x`** (K6): cạnh lên khởi động lại lane, lane vào Stop sau TINIT dù tín hiệu còn High. Bản cũ giữ lane ở INIT suốt thời gian tín hiệu High, nên thủ tục của controller (chỉ thả khi đã thấy Stop ít nhất T_INIT) bị kẹt | **Gửi dạng ghi chú** dưới K6 | Thủ tục của controller nay chạy được, mất khoảng 2 × TINIT. K6 vẫn mở |
| 8 | **Enable đổi lúc nào cũng được.** Tắt lane giữa burst thì burst kết thúc ngay ở PPI, và phần còn lại không được giao sau khi bật lại | **Gửi một dòng** ở phần cập nhật đầu file | Không đặt yêu cầu nào lên controller; đúng với ngữ nghĩa Enable của D-PHY |
| 9 | **`rxactivehs_x` chỉ lên từ cuối THS-SETTLE**, nên một HS entry bị hủy giữa chừng không còn tạo xung `rxactivehs_x` | **Gửi một dòng** | Thứ tự với `rxsynchs_x` không đổi. Burst FSM không còn gặp burst rỗng do HS entry bị hủy |
| 10 | **HAS-CSI Table 4-3 ghi `rxbyteclkhs` = "HS DDR clock divided by eight"**. Đúng ra là line rate / 8 = DDR clock / 4; con số 224 MHz ở 1792 Mb/s của họ đã đúng | **Gửi dạng ghi chú** dưới phụ lục C3 | Chỉ sửa câu chữ trong tài liệu của họ. HAS D-PHY có cùng lỗi tới v0.10 |
| 11 | `cl_rxclkactivehs` hạ tới khoảng 75 ns sau khi clock dừng (TCLK-MISS, đồng bộ, thanh ghi FSM). Từ v0.13: 50–60 ns sau cạnh cuối của DDR clock; v0.14 sửa thành chậm nhất 60 ns sau cạnh cuối, trong TCLK-MISS | **Không gửi** | Controller chỉ dùng tín hiệu này để chẩn đoán (C5) |

**HAS v0.12 và v0.13 chạm tới team CSI ở đâu.** v0.12 chỉ ghi rõ ranh giới AFE (đọc thành phương án
B), không đổi kỹ thuật. v0.13 sửa ranh giới thành phương án A, theo thông báo của team AFE ngày
2026-10-06. Sampler, deserializer 1:8, byte clock và phát hiện clock activity chuyển từ AFE vào
D-PHY Rx (Block No. 1). Tên, độ rộng và ngữ nghĩa các tín hiệu PPI giữ nguyên.

| # | Nội dung | Đề xuất | Lý do |
|---|---|---|---|
| 12 | **PPI không đổi ở v0.12 và v0.13**; `rxbyteclkhs` nay do D-PHY Rx tạo (DDR clock chia 4, qua clock gate) | **Gửi một dòng** ở phần cập nhật đầu file | Giúp team biết không cần xem lại waveform |
| 13 | **`rxbyteclkhs` bắt đầu chạy trong khoảng một byte clock sau khi `cl_rxclkactivehs` lên.** Clock gate của Block No. 1 chỉ mở khi clock lane đã vào CL_HS_CLK. HAS-CSI Table 4-3 lại ghi `cl_rxclkactivehs` nghĩa là "rxbyteclkhs is running" | **Gửi dạng ghi chú** dưới phụ lục C5 | Controller chỉ dùng tín hiệu này để chẩn đoán (C5), nên không phải đổi gì. Tuy vậy TB hoặc assertion của team CSI có thể dựa vào ngữ nghĩa đó. Cách khác, chỉ ảnh hưởng D-PHY: chỉ nâng `cl_rxclkactivehs` khi gate đã mở. Cách này thêm một crossing ngược về `core_clk`, và tín hiệu lên muộn hơn hiện nay khoảng một byte clock cộng 10–15 ns. Khi đó không cần gửi, nhưng phải sửa thêm HAS D-PHY §4.3 và §4.4 |
| 14 | **Rủi ro K1: chưa biết tốc độ tối đa của HS-RX.** Sơ đồ AFE tham khảo ghi 80–1000 Mb/s, trong khi HAS D-PHY R1 cần 1500 Mb/s và HAS-CSI cần trên 1500 Mb/s (1792 Mb/s). Phần digital của D-PHY Rx không còn là rủi ro chính: HAS v0.15 tính timing với cell 22 nm, công nghệ đích, thay cho 130 nm. Sampler (đặt tay) còn khoảng ±95 ps ở 1792 Mb/s cho lệch clock–data của AFE và phần digital, ở corner chậm 0.72 V/125 °C. Synthesis thử ở corner chậm, trước khi tính dây, đạt timing ở 1792 Mb/s: đường nửa chu kỳ của deserializer còn khoảng 360 ps (ước lượng 130 nm trước đây là gần 0). Các con số vẫn là ước lượng trước layout; thư viện, body bias và corner sign-off chưa chốt | **Chờ** câu trả lời A7 của team AFE, rồi mới gửi dưới K1 | Con số 1000 Mb/s lấy từ sơ đồ tham khảo, chưa phải thông số của team AFE, nên gửi sớm dễ gây hiểu lầm. Cách khác: gửi ngay dạng rủi ro, không kèm câu hỏi (đoạn tùy chọn ở Phần 2) |
| 15 | **Rủi ro C4 (R2): deskew cần delay line, mà AFE không có.** Delay line bằng cell chuẩn 22 nm có bước khoảng 15–30 ps tùy corner, trôi khoảng 2 lần, so với UI 558 ps ở 1792 Mb/s | **Chờ** câu trả lời A4 của team AFE, rồi mới gửi dưới K1 | R2 (1792 Mb/s, 4K staggered HDR) phụ thuộc A4. Cách khác: gửi ngay dạng rủi ro (đoạn tùy chọn ở Phần 2) |
| 16 | **224 MHz không còn là rủi ro timing phía D-PHY Rx.** Phần "Vì sao cần" của K1 trong `questions_csi_team.md` ghi `rxbyteclkhs` 224 MHz là rủi ro trên GF 130 nm. Synthesis thử với cell 22 nm, corner chậm 0.72 V/125 °C, trước layout: TNS bằng 0 ở 1792 và 1500 Mb/s, đường xấu nhất của `rxbyteclkhs` còn khoảng 0.95 ns | **Gửi một dòng** cùng đoạn rủi ro K1 (Phần 2) | Sửa một nhận định đã gửi. Số trước layout nên ghi là ước lượng |

**Những gì đã cập nhật trực tiếp** (theo kế hoạch đã duyệt, cũng chưa gửi):
- v0.9:
  - `questions_afe_team.md`: căn cứ lên v0.9; thêm A6 (độ trễ word Λ và dữ liệu trong THS-PREPARE); A2
    thêm lý do.
  - `questions_tx_side.md`: căn cứ lên v0.9; S5 không còn cần THS-ZERO max.
- v0.11:
  - `questions_afe_team.md`: căn cứ lên v0.11; byte clock = DDR clock chia 4; A3 sửa ngân sách
    termination (AFE chỉ còn 5–10 ns + 4·UI); A1 câu 4 thêm trường hợp `afe_cl_hs_en` bật hoặc tắt.
  - `questions_tx_side.md`: căn cứ lên v0.11; thêm S12; sửa câu "Rx chịu được toàn dải spec", vì nay
    có hai ngoại lệ (S5, S12).
- v0.12: `questions_afe_team.md`: căn cứ lên v0.12; ghi câu trả lời A1 ngày 2026-10-03, đọc thành
  phương án B.
- v0.13: `questions_afe_team.md`:
  - căn cứ lên v0.13; ranh giới sửa thành phương án A (team AFE, 2026-10-06);
  - A2 bỏ; A6 không còn hỏi Λ;
  - thêm A7–A11 (tốc độ HS-RX, chênh lệch trễ clock–data và duty cycle, đầu ra HS-RX khi tắt hoặc
    khởi động, số enable mỗi lane, đảo cực và map lane);
  - các ý còn mở của A1 chuyển sang A6, A8, A9 và A11. Ý 4 (trường hợp `afe_cl_hs_en` bật hoặc tắt)
    nay ở A9.

  `questions_tx_side.md` không đổi.

**Đã sửa trong bản nháp này:** mục ADR-007 không còn dẫn tới `doc/analysis/adr007/results.md`, là đường
dẫn team CSI không mở được. Mục này nay dẫn tới phần mô tả mô hình trong chương 7 của HAS D-PHY.

**Cần bạn quyết:** gửi những mục nào trong 1–3, 5–10 và 12–15? Mục 13 còn có cách sửa phía D-PHY
thay cho việc gửi. Nếu đồng ý, tôi chép Phần 2 vào `questions_csi_team.md`, cập nhật ngày, căn cứ và
bảng tóm tắt, rồi xóa file nháp này.

---

## Phần 2 — Bản nháp gửi team CSI

### Dòng cập nhật đầu file (thay dòng Ngày và Căn cứ)

| Mục | Nội dung |
|---|---|
| Ngày | 2026-09-26, cập nhật 2026-09-29 (thêm ADR-006; K3 thêm `eot_skip_bytes`), 2026-09-30 (ADR-006: điều đã biết từ HAS-CSI; phụ lục C6; waveform PPI), 2026-10-02 (ADR-007: leader hỏng, burst kết thúc trước khi lock; S12 mới; K6: `forcerxmode_x`; thay đổi PPI của v0.11), 2026-10-06 (v0.13: PPI không đổi; `rxbyteclkhs` do D-PHY Rx tạo, ghi chú ở phụ lục C5) và 2026-10-07 (v0.14: PPI không đổi; thời điểm `cl_rxclkactivehs` hạ ghi là cận trên 60 ns, phụ lục C5) |
| Căn cứ | HAS của `ftel_dphy_rx` bản nháp v0.14 (`hw/rtl/ip/ftel_dphy_rx/doc/spec.md`; bản Word `FTEL_IP_MIPI_D-PHY_RX_HAS_v0.14.docx`), HAS-CSI v1.2 |

Thêm vào cuối mục Bối cảnh:

> HAS v0.9 không đổi gì ở PPI. Thay đổi của v0.9 nằm bên trong D-PHY: điểm bắt đầu tìm sync (ADR-007).
>
> HAS v0.11 đổi ba điểm ở PPI:
> - Một burst kết thúc trước khi D-PHY lock có một xung `errsotsynchs_x` ở chu kỳ cuối của
>   `rxactivehs_x` (mục ADR-007, câu 3).
> - `rxactivehs_x` chỉ lên từ cuối THS-SETTLE. Một HS entry bị hủy giữa chừng (LP-11 trước khi hết
>   THS-SETTLE) không còn tạo xung `rxactivehs_x`. Thứ tự với `rxsynchs_x` không đổi.
> - `cl_enable` và `dl_enable_x` đổi lúc nào cũng được. Tắt lane giữa burst thì burst kết thúc ngay ở
>   PPI, và phần còn lại không được giao sau khi bật lại.
>
> HAS v0.12, v0.13 và v0.14 không đổi PPI. Theo thông báo của team AFE, v0.13 chuyển việc lấy mẫu bit HS,
> deserialize 1:8, tạo `rxbyteclkhs` và phát hiện clock activity từ AFE vào D-PHY Rx. Tên, độ rộng và
> ngữ nghĩa các tín hiệu PPI giữ nguyên; một điểm nhỏ về `cl_rxclkactivehs` ghi ở phụ lục C5.

### Dòng mới trong bảng Tóm tắt

| ID | Chủ đề | Ưu tiên | Yêu cầu đang chờ |
|---|---|---|---|
| ADR-007 | Sau một leader hỏng: khóa sai thay vì `errsotsynchs_x`; burst kết thúc trước khi lock | Trung bình | 2 |
| S12 | Số chu kỳ `rxbyteclkhs` controller cần sau byte cuối, trước khi clock lane rời HS | **Cao** | 4 |

### Ghi chú thêm vào cuối mục K3

> **Cập nhật v0.9.** Bảng giá trị `hs_settle_cyc` (HAS D-PHY Appendix B) đã đổi. Giá trị nay phụ thuộc
> thêm độ trễ word Λ, từ HAS D-PHY v0.13 do chính D-PHY Rx đặt. Với giả định hiện tại, 80 Mb/s là 70
> (trước là 39) và 1500 Mb/s là 19 (trước là 20). Số trường cấu hình không đổi.
>
> **Cập nhật v0.11.** `clk_settle_cyc` mặc định đổi từ 36 thành 33, để TCLK-SETTLE kết thúc giữa dải
> 95–300 ns. Số trường cấu hình không đổi.

### Ghi chú thêm vào cuối mục K6

> **Cập nhật v0.11.** `forcerxmode_x` nay có tác dụng ở cạnh lên. Lane quay về trạng thái khởi tạo và
> vào Stop sau khi thấy LP-11 trong `tinit_cyc`, kể cả khi tín hiệu vẫn High. Bản trước giữ lane ở
> trạng thái khởi tạo suốt thời gian tín hiệu High. Với cách HAS-CSI dùng tín hiệu này (chỉ bật khi lane
> đang ở Stop, chỉ thả khi đã thấy Stop ít nhất T_INIT), lane không bao giờ báo Stop và thủ tục bị kẹt.
> Nay thủ tục chạy được, mất khoảng 2 × TINIT (200 µs). Nhờ xác nhận ngữ nghĩa này.

### Ghi chú thêm vào phụ lục, dòng C3

> **Ghi chú.** HAS-CSI Table 4-3 ghi `rxbyteclkhs` là "HS DDR clock divided by eight". Một chu kỳ
> DDR clock dài 2 UI, nên byte clock = line rate / 8 = DDR clock / 4. Con số 224 MHz ở 1792 Mb/s
> của HAS-CSI đúng với line rate / 8, nên chỉ cần sửa câu chữ. HAS D-PHY có cùng lỗi câu chữ tới v0.10
> và đã sửa ở v0.11.

### Ghi chú thêm vào phụ lục, dòng C5 (mục 13 ở Phần 1)

> **Cập nhật v0.13, v0.14.** `rxbyteclkhs` nay do D-PHY Rx tạo: DDR clock của clock lane chia 4, qua một
> clock gate chỉ mở khi clock lane đã ở HS. Vì vậy `rxbyteclkhs` bắt đầu chạy trong khoảng một chu kỳ
> `rxbyteclkhs` sau khi `cl_rxclkactivehs` lên: khoảng 100 ns ở 80 Mb/s, 5.3 ns ở 1500 Mb/s.
> `cl_rxclkactivehs` hạ chậm nhất 60 ns sau cạnh cuối của DDR clock (TCLK-MISS); HAS D-PHY v0.13 ghi
> 50–60 ns, v0.14 sửa thành cận trên này. HAS-CSI Table 4-3 ghi tín hiệu này
> nghĩa là `rxbyteclkhs` đang chạy. Với cách controller dùng nó (chẩn đoán, C5), khoảng trễ này không
> ảnh hưởng. Nhờ xác nhận.

### (Tùy chọn, nếu chọn gửi ngay mục 14–16 ở Phần 1) Ghi chú thêm vào cuối mục K1

> **Rủi ro, cập nhật v0.13 và v0.15.** Theo thông báo của team AFE, AFE chỉ có HS-RX, LP-RX và termination;
> D-PHY Rx nay tự lấy mẫu và deserialize. Hai điểm có thể ảnh hưởng tốc độ lane:
> - Tốc độ tối đa của HS-RX đang được hỏi team AFE. Một sơ đồ AFE tham khảo ghi 80–1000 Mb/s; HAS
>   D-PHY R1 giả định 1500 Mb/s.
> - Deskew calibration (bắt buộc trên 1.5 Gb/s, C4) cần một delay line trước sampler. AFE hiện không
>   có delay line; một delay line bằng cell chuẩn 22 nm trôi khoảng 2 lần giữa các corner. R2
>   (1792 Mb/s) chờ câu trả lời của team AFE.
> - Phần digital của D-PHY Rx đạt timing ở 1792 Mb/s trong synthesis thử với cell 22 nm, công nghệ
>   đích (corner chậm, trước layout): đường nửa chu kỳ của deserializer còn khoảng 360 ps, và
>   `rxbyteclkhs` 224 MHz còn khoảng 0.95 ns. Vì vậy 224 MHz không còn là rủi ro như ghi ở mục này
>   trước đây (GF 130 nm). Physical design sẽ xác nhận sau layout (HAS D-PHY v0.15).
>
> Chưa có câu hỏi mới cho team CSI. Khi có câu trả lời của team AFE, chúng tôi sẽ cập nhật mục này.

### Mục mới (đặt trước Phụ lục)

## ADR-007 — Sau một leader hỏng

**Câu hỏi.**
1. HAS-CSI Figure 4-2 vẽ trường hợp leader hỏng: D-PHY báo `errsotsynchs_x`, và cả burst không có
   `rxsynchs_x` hay `rxvalidhs_x`. Thực tế, một leader có từ 2 bit lỗi trở lên thường vẫn khớp (cho
   phép sai 1 bit) ở một vị trí bit sai trước khi hết cửa sổ tìm sync `PARA_SYNC_SEARCH_BYTES`
   (16 chu kỳ `rxbyteclkhs`), mà phần lớn vị trí đó nằm trong payload. Khi đó D-PHY phát `rxsynchs_x`
   và `rxvalidhs_x` cho dữ liệu lệch byte, và không báo `errsotsynchs_x`. Controller có chấp nhận hành
   vi này không?
2. Nếu controller cần `errsotsynchs_x` trong trường hợp này, ví dụ để đếm đúng loại lỗi hoặc để abort
   sớm, team cần tới mức nào? Bảng dưới cho thấy cái giá phải trả.
3. Một burst kết thúc trước khi D-PHY lock và trước khi hết cửa sổ tìm sync, ví dụ một short packet
   trên 4 lane có leader hỏng. Từ HAS D-PHY v0.11, burst này có một xung `errsotsynchs_x` ở chu kỳ cuối
   của `rxactivehs_x`. Bản trước không có xung nào, và Burst FSM (HAS-CSI Table 4-6) hủy burst với
   nguyên nhân "unarmed". Nay burst vẫn bị hủy, nhưng với nguyên nhân errsotsynchs. Controller có chấp
   nhận không?

**Vì sao cần.**
- D-PHY chỉ nhận ra leader hỏng khi không vị trí nào khớp. Một chuỗi 8 bit ngẫu nhiên khớp leader
  (sai tối đa 1 bit) với xác suất khoảng 3.5 % ở mỗi vị trí, nên trong 16 chu kỳ gần như luôn có một
  vị trí khớp. Mô hình của chúng tôi cho kết quả khoảng 99 % leader hỏng dẫn tới khóa sai.
- Phía controller: với nhiều lane, lane khóa sai lệch byte so với các lane khác, nên dữ liệu ghép sai.
  Tùy lúc khóa và độ sâu FIFO, Burst FSM sẽ abort vì `fifo_full` thay vì vì `errsotsynchs`, hoặc dữ
  liệu lệch đi tiếp tới Packet Analyzer và bị ECC/CRC bắt. Với 1 lane, dữ liệu lệch đi thẳng tới
  Packet Analyzer.
- Trường hợp này hiếm, vì cần ít nhất 2 bit lỗi trong 8 bit leader.
- Câu 3: một burst ngắn hơn cửa sổ tìm sync kết thúc trước khi D-PHY kịp kết luận. Xung ở chu kỳ cuối
  cho controller cùng một tín hiệu cho mọi SoT không đồng bộ được.

Đánh đổi theo độ dài cửa sổ (mô hình của HAS D-PHY v0.9):

| `PARA_SYNC_SEARCH_BYTES` | Leader hỏng bị khóa sai (trên 1000) | Leader đúng, nhưng HS-0 trước nó có một bit lỗi đơn |
|---|---|---|
| 16 (mặc định) | khoảng 997 | vẫn nhận đúng, với bit lỗi ở bất kỳ vị trí nào trong 96 bit trước leader |
| 4 | khoảng 667 | mất burst nếu bit lỗi cách leader từ 17 bit trở lên |
| 2 | khoảng 401 | mất burst với mọi vị trí bit lỗi |

Rút ngắn cửa sổ chỉ giảm phần nào số lần khóa sai, và đổi lại làm mất burst khi HS-0 có một bit lỗi.

**Giả định hiện tại.** Giữ `PARA_SYNC_SEARCH_BYTES` = 16. Bit lỗi đơn trong HS-0 vẫn được chịu. Một
leader hỏng thường dẫn tới khóa sai, và lớp CSI-2 bắt lỗi bằng ECC/CRC. Burst kết thúc trước khi lock
có một xung `errsotsynchs_x` ở chu kỳ cuối.

**Tham chiếu.** HAS D-PHY v0.11 §4.6, §5.1, ADR-007 (mô hình bit-level mô tả trong chương 7), §8.
HAS-CSI Figure 4-2, Table 4-6 (Burst FSM), phần xử lý lỗi của Lane Management.

## S12 — Clock sau byte cuối, trước khi clock lane rời HS

**Câu hỏi.** Khi clock lane rời HS (vào ULPS, hoặc khi sensor dừng stream), `rxbyteclkhs` dừng. Sau
byte cuối của burst cuối ở PPI, Lane Management và các khối khác chạy trên `rxbyteclkhs` của controller
cần thêm bao nhiêu chu kỳ `rxbyteclkhs` để đẩy hết dữ liệu đi, ví dụ packet Frame End?

**Vì sao cần.**
- D-PHY Rx giữ đuôi mỗi burst trong một delay line để cắt trailer. Byte cuối ra PPI khoảng
  `PARA_EOT_DELAY_BYTES` + 3 chu kỳ `rxbyteclkhs` sau khi data lane về LP-11 (32 + 3 ở bản R1).
- Ở TCLK-POST tối thiểu của D-PHY, clock chỉ chạy thêm khoảng 7 chu kỳ ở 80 Mb/s và 18 chu kỳ ở
  1500 Mb/s. Phần đuôi, ví dụ Frame End, sẽ nằm lại trong D-PHY Rx và trong controller tới khi clock
  chạy lại.
- D-PHY cho phép phía Rx yêu cầu thêm clock: nếu receiver cần nhiều clock hơn TCLK-POST,min để nhận
  xong, transmitter phải cấp đủ. Chúng tôi hỏi phía Tx TCLK-POST ≥ 288·UI ở R1 (320·UI ở R2) cho phần
  của D-PHY Rx. Con số của controller sẽ cộng vào con số này.
- HAS-CSI ghi `rxbyteclkhs` dừng khi clock lane vào ULPS, và PHY Delay FIFO của Lane Management chạy
  trên `rxbyteclkhs`.

**Giả định hiện tại.** Chưa có. Con số hỏi phía Tx hiện chỉ gồm phần của D-PHY Rx (HAS D-PHY mục mở
S12).

**Tham chiếu.** HAS D-PHY v0.11 §4.6 (design note "clock after the last burst"), Appendix B dòng
TCLK-POST. HAS-CSI Table 4-1 (`rxbyteclkhs`), Lane Management.

### Dòng mới trong bảng Trả lời

| ID | Trả lời | Người trả lời | Ngày |
|---|---|---|---|
| ADR-007 | | | |
| S12 | | | |
