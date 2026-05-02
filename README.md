# 🧠 Mind Runner — EEG Brain Game

משחק Endless Runner הנשלט על ידי גלי מוח!

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

- **ריכוז > 65%** → השחקן מרחף מעל מכשולים נמוכים (סלעים)
- **מצמוץ** → קפיצה מעל מכשולים גבוהים (קירות)
- **Space / חצים** → שליטה במקלדת לצרכי בדיקה

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
