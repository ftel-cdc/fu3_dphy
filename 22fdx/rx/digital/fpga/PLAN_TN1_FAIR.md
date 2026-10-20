# Plan: TN1 so sánh công bằng phần digital RTL của hai RX (2026-10-20)

> Repo `/home/linhhk/Documents/DPHY`, branch `dev`, sau commit `465ff69`.
> Ký hiệu: ✅ đã kiểm (đọc code hoặc chạy thử) · ⚠️ ước lượng hoặc giả định · 🔍 kiểm khi làm.

## 0. Context

- Bạn hỏi (20/10): "cái tôi quan tâm là so sánh rtl digital thật công bằng trong tn1 này". Bạn duyệt plan
  ("tiếp tục đi"). Ở bước B, bạn chọn lái pad strong cho cả hai RX (xem §8).
- TN1 tại commit `465ff69` cho 113/113 kịch bản PASS với cả hai RX. Hai RX nhận cùng waveform trên pad, nhưng
  phần đứng trước digital RTL thì khác nhau, nên đó chưa phải phép so công bằng của riêng phần digital.

## 1. Hiện chưa công bằng ở 4 chỗ

| # | Chỗ khác nhau | RX AMD | RX mình |
|---|---|---|---|
| 1 | Front end | `IBUFDS_DPHY` (model của AMD) | `afe_model.sv` (mô hình mình tự viết) |
| 2 | LP trong lúc HS | Đổi theo data (model AMD, pad strong) | LP-00 |
| 3 | Stress EoT (E1-5: nhiễu, jitter, mọi pha `core_clk`, trail min/max) | Chưa chạy lần nào | 96 run |
| 4 | E1-3g (nhiễu AFE trong LP-00) | Không có tương đương | Là tính năng của `afe_model` |

## 2. Thay đổi

- **A. Front end chung.**
  - Testbench đặt `IBUFDS_DPHY` trước RTL mình, một buffer cho mỗi lane và một cho clock lane. Đây đúng
    primitive và đúng `SIM_DEVICE "VERSAL_PREMIUM"` mà IP AMD dùng ✅.
  - Cách nối: `LPRX_O_P/N` → `afe_lp_dp/dn`; `HSRX_O` → `afe_hs_bit` và `afe_cl_hs_clk`; `HSRX_DISABLE` ←
    `~hs_en` (`~cl_hs_en` cho clock lane); `LPRX_DISABLE` ← 0, như IP AMD (`lp_rx_disable_w` = 0) ✅.
  - Knob `+AFE=xil|model`, mặc định `xil`. `afe_model` vẫn chạy để kiểm trạng thái line và `term_en`, nhưng chỉ
    lái RTL khi `+AFE=model`.
- **B. Lái pad: strong cho cả hai** (bạn chọn ngày 20/10).
  - Bỏ phương án lái HS bằng pull, vì IP AMD tự đổi pad sang strong (§8).
  - Generator giữ nguyên. Cả hai buffer thấy cùng giá trị và cùng strength, nên ra cùng kết quả: LP đổi theo
    data trong HS, và HS-RX giữ bit cuối sau LP-11.
  - Bench thêm check: đầu ra LP của buffer AMD (wire `rx_dl<N>_lp_d<p|n>_w` và `rx_cl_lp_d<p|n>_w` trong
    `xrx_support`) phải trùng đầu ra LP của buffer trước RX mình ở mọi lần đổi. Build stub không có IP AMD nên
    không có check này (`` `ifndef TN1_STUB ``).
- **C. Cùng kịch bản stress.**
  - E1-5 chạy cả hai RX ở 8 rate (260, 400, 600, 800, 1000, 1200, 1440, 1500 Mb/s, 4 lane).
  - Cần thêm 4 build Vivado: 400, 600, 1000, 1200 Mb/s.
  - Giới hạn trailer vẫn chỉ áp cho RX mình, vì RX AMD theo thiết kế không cắt trailer.
- **D. E1-3g** chỉ chạy với `+AFE=model`, vì nhiễu là của `afe_model`; ghi là test riêng của RX mình.
- **E. Chạy lại toàn bộ ở chế độ công bằng.**
  - Kết quả ngày 20/10 (RX mình sau `afe_model`) được lưu ở `fpga/work/exp1/_v016_model` và giữ làm cột phụ
    "RX mình sau `afe_model` (LP-00 trong HS như silicon)".
  - Kiểm bench mới ở `+AFE=model` ra đúng capture cũ, để cột phụ vẫn khớp với bench hiện tại.
  - `run_exp1.sh window` (phép đo của HAS Table 4-7) chạy với `+AFE=model`, như lúc đo.
- **F. Kiểm chứng và tài liệu.**
  - `tn1_evidence.py` thêm check `front`: mỗi run hai RX có hai front end trùng nhau, và RX mình đứng sau
    `IBUFDS_DPHY`, trừ các kịch bản tự chọn `+AFE=model`.
  - `fpga/exp1/README.md` cập nhật §2–§9; `fpga/README.md`; ghi chú trong `PLAN_TN1_TN3.md` và
    `doc/rtl_notes.md` §9.

## 3. Vẫn khác sau khi sửa (do thiết kế, sẽ ghi rõ)

- **Deserializer:** AMD dùng XPHY (khối cứng), mình dùng Block No. 1 (RTL). Mỗi bên so trọn đường digital của
  mình, tính từ đầu ra buffer. Muốn giống hệt tới tận deserializer thì phải làm TN2c.
- **Điều khiển HS-RX:** mỗi RX tự bật HS-RX bằng logic của mình (`hs_en` của mình, `disable_ibuf` của AMD). Đây
  là một phần của digital RTL được so.
- **Cấu hình:** AMD để mặc định của IP; RX mình dùng giá trị model HAS.

## 4. Rủi ro

1. **Byte trailer khác Table 4-7.** Đã đo ở probe (§8): RX mình sau `IBUFDS_DPHY` cho trailer bằng hoặc ít hơn
   sau `afe_model`. Table 4-7 không đổi.
2. **X đầu mô phỏng.** `HSRX_O` của model là X khi `HSRX_DISABLE` là X. Nếu X lọt vào RTL mình mà AMD không bị,
   đó là hiện tượng chỉ có trong mô phỏng; tôi báo bạn trước khi xử lý. Probe chưa thấy X ✅.
3. **RX mình gặp LP đổi trong HS.** Probe: 110/110 PASS không sửa RTL ✅. Lý do: `dl_ctrl` ở trạng thái HS chỉ
   phản ứng với LP-11, và LP-11 phải ổn định 3 mẫu `core_clk` (`m_ftel_dphy_rx_lp_filter`).
4. **Đường hierarchy vào IP AMD** đổi theo phiên bản IP. Nếu Vivado sinh IP khác tên, check `front` báo lỗi
   compile thay vì im lặng.

## 5. Kiểm chứng

- `tn1_evidence.py` PASS mọi check, gồm `front`.
- Check trùng đầu ra buffer: 0 lần khác nhau, số lần so > 0, ở mọi run hai RX.
- Bench mới ở `+AFE=model` ra capture giống từng byte với capture ngày 20/10, trừ kịch bản dùng số ngẫu nhiên
  không seed (E1-2b).
- `run_exp1.sh summary` toàn PASS.

## 6. Thứ tự và ước lượng ⚠️

| Bước | Việc | Ước lượng |
|---|---|---|
| 1 | Lưu plan; sửa `tb_exp1.sv`, `run_exp1.sh` | 0,1 ngày |
| 2 | Build lại 7 build và thêm 4 build (chạy song song) | khoảng 15 phút máy |
| 3 | Lưu kết quả cũ; kiểm bench mới ở `+AFE=model`; chạy lại toàn bộ (E1-5 chạy song song theo rate) | khoảng 30 phút máy |
| 4 | `tn1_evidence.py`, README, ghi chú; cập nhật memory | 0,3 ngày |

## 7. Độ tin cậy

- **HIGH:** IP AMD đưa pad qua `assign` thường nên buffer của AMD thấy strong; A và B làm được (probe đã chạy).
- **MED:** thời gian chạy thực tế của E1-5 khi có cả hai RX.

## 8. Phát hiện khi làm (2026-10-20)

- **Plan B ban đầu: lái HS bằng pull** để cả hai buffer thấy LP-00 trong HS như silicon. Probe XSIM cho thấy
  `IBUFDS_DPHY` ra LP-00 khi cả hai pin có strength pull.
- **Nhưng IP AMD đưa pad qua `assign` thường** ✅ (`xrx_core.v`, dòng 447–459 của IP sinh ra: `assign dl_rxp[0] =
  data_rxp[0]` ...). Theo chuẩn Verilog, `assign` không khai báo strength thì lái strong. Vì vậy buffer của AMD
  luôn thấy strong, dù testbench lái pad kiểu gì. Lái pull chỉ làm buffer của RX mình khác buffer của AMD.
- **Probe (scratchpad, chỉ RX mình, build stub):** RX mình sau `IBUFDS_DPHY` lái strong đạt 110/110 kịch bản
  (E1-1…E1-4 và 96 run E1-5, giới hạn trailer theo Table 4-7), không sửa RTL.
  - So với `afe_model`: 103 run cho trailer và payload trùng hệt.
  - 7 run ở 260/400 Mb/s không nhiễu cho ít trailer hơn (0 thay vì tối đa 2–4 byte). Lý do: model AMD giữ bit
    trail sau LP-11, còn `afe_model` ép về 0.
- **Bạn chọn strong cho cả hai** (20/10).

## 9. Kết quả (2026-10-20)

**Trạng thái:** đã làm xong, chưa commit. TN1 ở chế độ công bằng: 113/113 kịch bản PASS cho cả hai RX
(`fpga/exp1/run_exp1.sh summary`). `tn1_evidence.py`: EVIDENCE PASS 8/8.

**Đã làm:**
- `tb_exp1.sv`:
  - `IBUFDS_DPHY` trước RTL mình; `+AFE=xil|model`;
  - check trùng đầu ra LP với buffer của AMD (`TB FRONT END CHECK`, không có ở build stub, `TN1_STUB`);
  - ba nhánh generate của `xrx` cùng tên `g_x`.
- `run_exp1.sh`:
  - build stub thêm `unisims_ver` và `glbl`;
  - E1-3g với `+AFE=model`;
  - E1-5 chạy cả hai RX và nhận danh sách rate;
  - `window` với `+AFE=model`;
  - lệnh `model` (bộ phụ `M_<tên>`).
- `tn1_evidence.py`: check `front`.
- `neg_front.sh`: phép thử âm của check `front`, chạy trên bản copy của build 1440 Mb/s và không đụng nguồn.
- 4 build mới: 400, 600, 1000, 1200 Mb/s.
- Kết quả ngày 20/10 cũ lưu ở `fpga/work/exp1/_v016_model`.

**Kết quả:**
- **Chế độ công bằng:** cả hai RX nhận đúng mọi payload ở mọi kịch bản, kể cả E1-5 ở 8 rate (mỗi ô 432/432 cho mỗi
  RX).
  - RX mình: 0 byte trailer khi không nhiễu, ở mọi rate.
  - Có 40 ns nhiễu: trailer trong giới hạn Table 4-7, lớn nhất 4 ở 260 Mb/s và 12 ở 1440 Mb/s.
  - RX AMD giữ trailer: 1–4 byte ở 260 Mb/s, tới 25 byte ở 1500 Mb/s.
- **Front end:** 226/226 run hai RX, 4 854 302 lần so đầu ra LP của hai bộ buffer, 0 khác.
  - Phép thử âm (buffer của RX mình thấy pull trong HS): 21 574 / 30 450 lần đổi khác, `front` FAIL.
- **Bộ phụ `M_*`** (RX mình sau `afe_model`): 113/113 PASS. `truth.txt` và capture giống từng byte với lần chạy
  trước khi đổi bench (500/500 file, gồm 128 run `window`). Table 4-7 và check `margin` không đổi.
- **RX mình sau `IBUFDS_DPHY` so với sau `afe_model`:** trailer bằng hoặc ít hơn. Ở 260 và 400 Mb/s không nhiễu
  còn 0 byte, thay vì 0–4 byte ở 67 và 4 trong 432 burst. Lý do: model AMD giữ bit trail sau LP-11.
- **Thời gian:** toàn bộ (113 + 113 kịch bản, R-80, `window`) chạy trong 13 phút, chia 2 pha song song. RAM trống
  thấp nhất 22,1 GB.

**Khác với plan:**
- Bước B đổi thành strong cho cả hai, xem §8.
- Ước lượng "build lại khoảng 15 phút":
  - 6 build cũ chỉ compile lại testbench, mất vài giây;
  - 4 build mới mất khoảng 5–8 phút khi chạy song song.
- Thêm lệnh `model`, để cột phụ được sinh lại từ bench hiện tại chứ không chỉ là bản lưu.
- Nhãn `TB FRONT END` của các run `afe_model` bị `%s` đệm khoảng trắng (toán tử `?:` giữa hai string literal ra
  giá trị integral). Đây chỉ là chữ in ra; regex của `tn1_evidence.py` đã chịu được khoảng trắng này. Bench
  không đổi nên không phải chạy lại.

Chi tiết và bảng số: `fpga/exp1/README.md` §6–§7.
