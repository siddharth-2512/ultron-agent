import json
import os
import threading
import urllib.request
import cv2
import mysql.connector
from mysql.connector import Error
import tkinter as tk
from datetime import datetime
from PIL import Image, ImageTk
import voice_module
import sqlite3

class UltronClinicalDashboard:

    def __init__(self, root):
        self.root = root
        self.root.title("ULTRON — Ward 4B Clinical Dashboard")
        self.root.geometry("1150x780")
        self.root.configure(bg="#F5F2EC")

        # Database Configuration
        self.db_config = {
            "host": "localhost",
            "port": 3306,  # Standard MySQL port
            "user": "root",
            "password": "your_mysql_password",
            "database": "hospital_db",
        }

        # Computer Vision Setup
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

        self.running = True
        self.prev_y = None
        self.fall_threshold = 85
        self.fall_counter = 0
        self.fall_confirmed_frames = 2

        self._build_ui()

        # Start background database polling (every 5000 ms)
        self.fetch_database_data()

        # Camera Initialization
        self.cap = cv2.VideoCapture(0)
        self.update_video()

    def get_db_connection(self):
        try:
            conn = sqlite3.connect("hospital.db")
            conn.row_factory = sqlite3.Row  # Access columns by name
            return conn
        except Exception as err:
            self.log(f"[DB Error]: {err}")
            return None

    def fetch_database_data(self):
        """Fetches live patient vital records directly from MySQL database."""
        if not self.running:
            return

        conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT bed_id, patient_name, status, hr, bp, spo2, temp FROM patients ORDER BY bed_id ASC;"
                )
                patients = cursor.fetchall()
                self._render_patient_cards(patients)
            except Error as err:
                self.log(f"[DB Query Error]: {err}")
            finally:
                conn.close()

        # Refresh database query after 5 seconds
        self.root.after(5000, self.fetch_database_data)

    def _build_ui(self):
        # 1. Top Bar
        navbar = tk.Frame(self.root, bg="#F5F2EC", height=60)
        navbar.pack(fill=tk.X, side=tk.TOP, padx=25, pady=(15, 10))
        navbar.pack_propagate(False)

        brand_frame = tk.Frame(navbar, bg="#F5F2EC")
        brand_frame.pack(side=tk.LEFT)

        icon_lbl = tk.Label(
            brand_frame,
            text="⚕",
            font=("Segoe UI", 16, "bold"),
            fg="#2563EB",
            bg="#DCE7FE",
            width=2,
            height=1,
        )
        icon_lbl.pack(side=tk.LEFT, padx=(0, 10))

        title_box = tk.Frame(brand_frame, bg="#F5F2EC")
        title_box.pack(side=tk.LEFT)

        tk.Label(
            title_box,
            text="ULTRON",
            font=("Segoe UI", 16, "bold"),
            fg="#0F172A",
            bg="#F5F2EC",
        ).pack(anchor="w")
        tk.Label(
            title_box,
            text="Ward 4B · live database integration",
            font=("Segoe UI", 9),
            fg="#64748B",
            bg="#F5F2EC",
        ).pack(anchor="w")

        right_nav = tk.Frame(navbar, bg="#F5F2EC")
        right_nav.pack(side=tk.RIGHT)

        self.alert_badge = tk.Label(
            right_nav,
            text="⚠️ 1 alert",
            font=("Segoe UI", 9, "bold"),
            fg="#991B1B",
            bg="#FEE2E2",
            padx=10,
            pady=4,
        )
        self.alert_badge.pack(side=tk.LEFT, padx=10)

        profile_icon = tk.Label(
            right_nav,
            text="👤",
            font=("Segoe UI", 12),
            fg="#0F172A",
            bg="#E2E8F0",
            width=2,
            height=1,
        )
        profile_icon.pack(side=tk.LEFT)

        # 2. Alert Banner
        self.banner = tk.Frame(
            self.root,
            bg="#FEF2F2",
            highlightbackground="#FCA5A5",
            highlightthickness=1,
        )
        self.banner.pack(fill=tk.X, padx=25, pady=(0, 15))

        banner_content = tk.Frame(self.banner, bg="#FEF2F2")
        banner_content.pack(fill=tk.X, padx=15, pady=12)

        self.video_frame = tk.Label(
            banner_content, bg="#000000", width=200, height=110
        )
        self.video_frame.pack(side=tk.LEFT, padx=(0, 15))

        banner_text_box = tk.Frame(banner_content, bg="#FEF2F2")
        banner_text_box.pack(side=tk.LEFT, fill=tk.Y)

        self.banner_title = tk.Label(
            banner_text_box,
            text="♥ Bed 3 — R. Fernandez",
            font=("Segoe UI", 11, "bold"),
            fg="#991B1B",
            bg="#FEF2F2",
        )
        self.banner_title.pack(anchor="w")

        self.banner_sub = tk.Label(
            banner_text_box,
            text="BP 168/104 — above threshold for 6 min",
            font=("Segoe UI", 9),
            fg="#B91C1C",
            bg="#FEF2F2",
        )
        self.banner_sub.pack(anchor="w", pady=(2, 0))

        self.ack_btn = tk.Button(
            banner_content,
            text="Acknowledge",
            font=("Segoe UI", 9, "bold"),
            fg="#991B1B",
            bg="#FFFFFF",
            activebackground="#FEE2E2",
            bd=1,
            relief="solid",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self.acknowledge_alert,
        )
        self.ack_btn.pack(side=tk.RIGHT, padx=10)

        # 3. Main Split Container
        grid_container = tk.Frame(self.root, bg="#F5F2EC")
        grid_container.pack(fill=tk.BOTH, expand=True, padx=25, pady=(0, 15))

        self.cards_frame = tk.Frame(grid_container, bg="#F5F2EC")
        self.cards_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Right Log Panel
        log_panel = tk.Frame(
            grid_container,
            bg="#FFFFFF",
            bd=1,
            relief="solid",
            highlightbackground="#E2E8F0",
            width=320,
        )
        log_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        log_panel.pack_propagate(False)

        tk.Label(
            log_panel,
            text="VOICE & AI TERMINAL LOG",
            font=("Segoe UI", 9, "bold"),
            fg="#64748B",
            bg="#FFFFFF",
        ).pack(anchor="w", padx=12, pady=(10, 5))

        self.log_box = tk.Text(
            log_panel,
            bg="#FAFAFA",
            fg="#334155",
            font=("Consolas", 9),
            bd=0,
            padx=10,
            pady=8,
            wrap=tk.WORD,
        )
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # 4. Command Input Bar
        bottom_bar = tk.Frame(
            self.root,
            bg="#FFFFFF",
            highlightbackground="#E2E8F0",
            highlightthickness=1,
        )
        bottom_bar.pack(fill=tk.X, padx=25, pady=(0, 20))

        bar_inner = tk.Frame(bottom_bar, bg="#FFFFFF")
        bar_inner.pack(fill=tk.X, padx=15, pady=8)

        self.listen_btn = tk.Button(
            bar_inner,
            text="🎤 Ask ULTRON",
            font=("Segoe UI", 9, "bold"),
            fg="#2563EB",
            bg="#EFF6FF",
            activebackground="#DBEAFE",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self.trigger_voice,
        )
        self.listen_btn.pack(side=tk.LEFT)

        tk.Label(
            bar_inner,
            text='—  "Summarize bed 3\'s last hour" or "Flag any patient above threshold"',
            font=("Segoe UI", 9),
            fg="#94A3B8",
            bg="#FFFFFF",
        ).pack(side=tk.LEFT, padx=10)

    def _render_patient_cards(self, patients):
        """Destroys old widgets and renders live records from MySQL."""
        for widget in self.cards_frame.winfo_children():
            widget.destroy()

        row, col = 0, 0
        for p in patients:
            card = self._create_patient_card(self.cards_frame, p)
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            col += 1
            if col > 2:
                col = 0
                row += 1

        for r in range(2):
            self.cards_frame.grid_rowconfigure(r, weight=1)
        for c in range(3):
            self.cards_frame.grid_columnconfigure(c, weight=1)

    def _create_patient_card(self, parent, p):
        bg_color = "#FFFFFF"
        border_color = "#E2E8F0"
        dot_color = "#22C55E"

        if p["status"] == "critical":
            bg_color = "#FEF2F2"
            border_color = "#FCA5A5"
            dot_color = "#EF4444"
        elif p["status"] == "warning":
            dot_color = "#F59E0B"
        elif p["status"] == "empty":
            dot_color = "#94A3B8"

        card = tk.Frame(
            parent,
            bg=bg_color,
            highlightbackground=border_color,
            highlightthickness=1,
            padx=12,
            pady=10,
        )

        header = tk.Frame(card, bg=bg_color)
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text=f"Bed {p['bed_id']} — {p['patient_name']}",
            font=("Segoe UI", 10, "bold"),
            fg="#0F172A" if p["status"] != "critical" else "#991B1B",
            bg=bg_color,
        ).pack(side=tk.LEFT)

        tk.Label(
            header, text="●", font=("Segoe UI", 8), fg=dot_color, bg=bg_color
        ).pack(side=tk.RIGHT)

        if p["status"] != "empty":
            body = tk.Frame(card, bg=bg_color)
            body.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

            left_col = tk.Frame(body, bg=bg_color)
            left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            tk.Label(
                left_col, text="HR", font=("Segoe UI", 8), fg="#94A3B8", bg=bg_color
            ).pack(anchor="w")
            tk.Label(
                left_col,
                text=p["hr"],
                font=("Segoe UI", 9, "bold"),
                fg="#0F172A",
                bg=bg_color,
            ).pack(anchor="w")
            tk.Label(
                left_col,
                text="SpO2",
                font=("Segoe UI", 8),
                fg="#94A3B8",
                bg=bg_color,
            ).pack(anchor="w", pady=(4, 0))
            tk.Label(
                left_col,
                text=p["spo2"],
                font=("Segoe UI", 9, "bold"),
                fg="#0F172A",
                bg=bg_color,
            ).pack(anchor="w")

            right_col = tk.Frame(body, bg=bg_color)
            right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

            tk.Label(
                right_col, text="BP", font=("Segoe UI", 8), fg="#94A3B8", bg=bg_color
            ).pack(anchor="w")
            tk.Label(
                right_col,
                text=p["bp"],
                font=("Segoe UI", 9, "bold"),
                fg="#0F172A" if p["status"] != "critical" else "#991B1B",
                bg=bg_color,
            ).pack(anchor="w")
            tk.Label(
                right_col,
                text="Temp",
                font=("Segoe UI", 8),
                fg="#94A3B8",
                bg=bg_color,
            ).pack(anchor="w", pady=(4, 0))
            tk.Label(
                right_col,
                text=p["temp"],
                font=("Segoe UI", 9, "bold"),
                fg="#0F172A",
                bg=bg_color,
            ).pack(anchor="w")
        else:
            tk.Label(
                card,
                text="No patient assigned",
                font=("Segoe UI", 9),
                fg="#94A3B8",
                bg=bg_color,
            ).pack(anchor="w", pady=(12, 0))

        return card

    def log(self, message):
        self.log_box.insert(tk.END, f"{message}\n\n")
        self.log_box.see(tk.END)

    def acknowledge_alert(self):
        self.banner.config(bg="#F8FAFC", highlightbackground="#CBD5E1")
        self.banner_title.config(
            text="All Alerts Acknowledged", fg="#475569", bg="#F8FAFC"
        )
        self.banner_sub.config(
            text="Monitoring active for 6 beds.", fg="#64748B", bg="#F8FAFC"
        )
        self.alert_badge.config(text="✓ 0 alerts", fg="#166534", bg="#DCFCE7")
        self.log("[System]: Emergency Alert Acknowledged by Staff.")

    def update_video(self):
        if not self.running:
            return

        ret, frame = self.cap.read()
        if ret:
            resized = cv2.resize(frame, (200, 110))
            boxes, _ = self.hog.detectMultiScale(
                resized, winStride=(8, 8), padding=(4, 4), scale=1.05
            )

            if len(boxes) > 0:
                largest_box = max(boxes, key=lambda b: b[2] * b[3])
                x, y, w, h = largest_box
                cv2.rectangle(resized, (x, y), (x + w, y + h), (0, 255, 0), 2)

                if self.prev_y is not None:
                    delta_y = y - self.prev_y
                    if delta_y > self.fall_threshold:
                        self.fall_counter += 1
                    else:
                        self.fall_counter = max(0, self.fall_counter - 1)

                    if self.fall_counter >= self.fall_confirmed_frames:
                        cv2.putText(
                            resized,
                            "FALL!",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 0, 255),
                            2,
                        )
                        self.banner.config(
                            bg="#FEF2F2", highlightbackground="#EF4444"
                        )
                        self.banner_title.config(
                            text="CRITICAL: FALL DETECTED ON CAMERA!",
                            fg="#991B1B",
                        )
                        self.alert_badge.config(
                            text="⚠️ CRITICAL FALL", fg="#991B1B", bg="#FEE2E2"
                        )

                self.prev_y = y

            rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb_frame)
            imgtk = ImageTk.PhotoImage(image=img)
            self.video_frame.imgtk = imgtk
            self.video_frame.configure(image=imgtk)

        self.root.after(30, self.update_video)

    def trigger_voice(self):
        threading.Thread(target=self._voice_task, daemon=True).start()

    def query_ai(self, user_prompt):
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return "Set OPENROUTER_API_KEY environment variable."

        db_context = "No database data currently loaded."
        conn = self.get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT bed_id, patient_name, status, hr, bp, spo2, temp FROM patients;"
                )
                rows = cursor.fetchall()
                db_context = json.dumps(rows)
            finally:
                conn.close()

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "auto",
            "messages": [
                {
                    "role": "system",
                    "content": f"You are ULTRON, a concise clinical assistant. Provide clear answers based on patient database: {db_context}",
                },
                {"role": "user", "content": user_prompt},
            ],
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["choices"][0]["message"]["content"].strip()
        except Exception as err:
            return f"API Error: {err}"

    def _voice_task(self):
        self.listen_btn.config(text="🎙️ Listening...", bg="#FDE047", fg="#854D0E")
        self.log("[Audio Engine]: Listening for voice input...")

        raw_cmd = voice_module.listen_command()

        if raw_cmd:
            cmd = raw_cmd.lower().strip()
            self.log(f"👤 User: '{cmd}'")

            if any(k in cmd for k in ["time", "clock"]):
                current_time = datetime.now().strftime("%I:%M %p")
                response = f"The current time is {current_time}."
            elif any(k in cmd for k in ["date", "today"]):
                current_date = datetime.now().strftime("%A, %B %d, %Y")
                response = f"Today is {current_date}."
            else:
                self.log("🤖 OpenRouter AI Thinking...")
                response = self.query_ai(cmd)

            self.log(f"⚡ ULTRON: {response}")
            voice_module.speak(response)
        else:
            self.log("[Audio Engine]: Speech uncaptured or timed out.")

        self.listen_btn.config(text="🎤 Ask ULTRON", bg="#EFF6FF", fg="#2563EB")

    def on_close(self):
        self.running = False
        if self.cap.isOpened():
            self.cap.release()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = UltronClinicalDashboard(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()