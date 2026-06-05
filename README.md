# 🧠 Mind Runner 3D — EEG Brain Game

משחק Endless Runner **תלת-ממדי** הנשלט על ידי גלי מוח — בסטייל של Temple Run / Subway Surfers.
הדמות רצה לתוך המסך על מסלול ניאון עם תאורה, צללים, ערפל וזוהר (bloom).

> מנוע הרינדור: **Three.js** (נטען מ-CDN). הטעינה הראשונה דורשת חיבור אינטרנט.

## התקנה מהירה

### דרישות

- Python 3.8+
- מכשיר Mind Link / MindWave Mobile מחובר בבלוטות'
- ThinkGear Connector מותקן (הורד מ-neurosky.com)

### הפעלה

1. חבר את Mind Link בבלוטות'
2. הפעל את ThinkGear Connector
3. הרץ:
   ```bash
   pip install -r requirements.txt
   python bridge.py
   ```
4. פתח: `https://<username>.github.io/mindlink-game`

### אפשרויות נוספות ל-bridge.py

```bash
python bridge.py --port COM5        # ציין port ידנית
python bridge.py --port /dev/rfcomm0
python bridge.py --demo             # מצב demo בכפייה
```

### מצב Demo (ללא מכשיר)

פשוט פתח את הלינק — יעבור אוטומטית למצב Demo אחרי 5 שניות.  
גם בלי `bridge.py` בכלל, המשחק פועל עם נתונים מסונתזים.

## מכניקת המשחק

- **ריכוז ≥ סף** → הדמות **מרחפת** מעל מחסומים שעל הקרקע (ציאן)
- **מצמוץ** → **קפיצה** מעל מחסומים שעל הקרקע
- **שערים נמוכים מלמעלה (מגנטה)** → צריך **להישאר נמוך**: הורד ריכוז ואל תקפוץ, אחרת תיפגע
- 3 חיים, מהירות עולה עם הניקוד, חסינות קצרה אחרי פגיעה

### שליטה במקלדת (בדיקה / Demo)

- **Space** — מצמוץ (קפיצה) / התחלה / משחק מחדש
- **חץ למעלה / למטה** — העלאה/הורדה של ערך הריכוז
- **[ / ]** — הורדה/העלאה של סף הריכוז (ברירת מחדל 50%)

## מבנה הפרויקט

```
mindlink-game/
├── index.html       ← המשחק המלא (קובץ יחיד, עובד ב-GitHub Pages)
├── bridge.py        ← WebSocket bridge (מחשב המורה)
├── requirements.txt
└── README.md
```

## GitHub Pages

הפרויקט מוגדר לעבוד עם GitHub Pages ישירות מ-`index.html`.  
אין צורך בשרת — המשחק הוא קובץ סטטי בלבד.
