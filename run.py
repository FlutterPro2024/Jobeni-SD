import os
from app import create_app

# هذا هو الكائن الذي يبحث عنه Vercel
app = create_app('production' if os.environ.get('VERCEL') else 'default')

if __name__ == "__main__":
    app.run()
