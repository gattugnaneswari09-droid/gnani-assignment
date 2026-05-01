from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from datetime import datetime
import re
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key_here_12345'

# MongoDB Connection
try:
    client = MongoClient('mongodb://localhost:27017/')
    db = client['assignment_evaluation_db']
    evaluations_collection = db['evaluations']
    print("✅ Connected to MongoDB successfully!")
    print("📊 Database: assignment_evaluation_db")
    print("📁 Collection: evaluations")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")
    print("Please make sure MongoDB is running on localhost:27017")

# Evaluation Logic Class
class AssignmentEvaluator:
    def __init__(self):
        self.keywords_weight = 0.7
        self.similarity_weight = 0.3
    
    def extract_keywords(self, text):
        """Extract important keywords from text"""
        # Remove common words and punctuation
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'but', 'not', 'so', 'very', 'just', 'than', 'then', 'now', 'can', 'will', 'would', 'should', 'could', 'may', 'might', 'must'}
        
        # Clean text
        text_clean = re.sub(r'[^\w\s]', '', text.lower())
        words = text_clean.split()
        
        # Filter keywords
        keywords = [word for word in words if word not in common_words and len(word) > 2]
        return keywords
    
    def calculate_keyword_match(self, student_keywords, correct_keywords):
        """Calculate keyword matching score"""
        if not correct_keywords:
            return 0
        
        matched = 0
        for keyword in correct_keywords:
            if keyword in student_keywords:
                matched += 1
        
        return (matched / len(correct_keywords)) * 100
    
    def calculate_similarity(self, student_answer, correct_answer):
        """Calculate basic text similarity"""
        student_words = set(re.sub(r'[^\w\s]', '', student_answer.lower()).split())
        correct_words = set(re.sub(r'[^\w\s]', '', correct_answer.lower()).split())
        
        if not correct_words:
            return 0
        
        intersection = student_words.intersection(correct_words)
        union = student_words.union(correct_words)
        
        if union:
            return (len(intersection) / len(union)) * 100
        return 0
    
    def evaluate(self, student_answer, correct_answer):
        """Main evaluation function"""
        # Extract keywords
        student_keywords = self.extract_keywords(student_answer)
        correct_keywords = self.extract_keywords(correct_answer)
        
        # Calculate scores
        keyword_score = self.calculate_keyword_match(student_keywords, correct_keywords)
        similarity_score = self.calculate_similarity(student_answer, correct_answer)
        
        # Combined score
        total_score = (keyword_score * self.keywords_weight) + (similarity_score * self.similarity_weight)
        
        # Generate feedback
        if total_score >= 80:
            feedback = "Excellent! Your answer is very well-written and covers all key points perfectly."
            grade = "A"
        elif total_score >= 70:
            feedback = "Good job! Your answer is correct but could include a few more details."
            grade = "B"
        elif total_score >= 60:
            feedback = "Satisfactory. Your answer is partially correct. Review the key concepts."
            grade = "C"
        elif total_score >= 50:
            feedback = "Needs improvement. Your answer misses several important points."
            grade = "D"
        else:
            feedback = "Insufficient. Please review the topic thoroughly and try again."
            grade = "F"
        
        # Calculate score out of 10
        score_out_of_10 = round(total_score / 10, 1)
        
        return {
            'score_percentage': round(total_score, 2),
            'score_out_of_10': score_out_of_10,
            'keyword_match': round(keyword_score, 2),
            'similarity': round(similarity_score, 2),
            'feedback': feedback,
            'grade': grade,
            'student_keywords_found': len(student_keywords),
            'total_keywords_expected': len(correct_keywords),
            'keywords_matched': len([k for k in correct_keywords if k in student_keywords])
        }

# Initialize evaluator
evaluator = AssignmentEvaluator()

# Routes
@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/evaluate', methods=['POST'])
def evaluate_assignment():
    """API endpoint for assignment evaluation"""
    try:
        data = request.get_json()
        
        student_answer = data.get('student_answer', '').strip()
        correct_answer = data.get('correct_answer', '').strip()
        
        # Validate inputs
        if not student_answer:
            return jsonify({
                'success': False,
                'error': 'Student answer cannot be empty'
            }), 400
        
        if not correct_answer:
            return jsonify({
                'success': False,
                'error': 'Correct answer cannot be empty'
            }), 400
        
        # Perform evaluation
        evaluation_result = evaluator.evaluate(student_answer, correct_answer)
        
        # Store in database
        evaluation_document = {
            'student_answer': student_answer,
            'correct_answer': correct_answer,
            'score_percentage': evaluation_result['score_percentage'],
            'score_out_of_10': evaluation_result['score_out_of_10'],
            'keyword_match': evaluation_result['keyword_match'],
            'similarity': evaluation_result['similarity'],
            'feedback': evaluation_result['feedback'],
            'grade': evaluation_result['grade'],
            'keywords_matched': evaluation_result['keywords_matched'],
            'total_keywords': evaluation_result['total_keywords_expected'],
            'timestamp': datetime.now()
        }
        
        # Insert into MongoDB
        result_id = evaluations_collection.insert_one(evaluation_document)
        
        # Prepare response
        response = {
            'success': True,
            'evaluation_id': str(result_id.inserted_id),
            'results': evaluation_result,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        print(f"Error in evaluation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_statistics():
    """Get evaluation statistics"""
    try:
        total_evaluations = evaluations_collection.count_documents({})
        
        # Calculate average score
        pipeline = [
            {'$group': {
                '_id': None,
                'avg_score': {'$avg': '$score_percentage'},
                'avg_keyword_match': {'$avg': '$keyword_match'},
                'avg_similarity': {'$avg': '$similarity'},
                'total': {'$sum': 1}
            }}
        ]
        
        result = list(evaluations_collection.aggregate(pipeline))
        
        if result:
            stats = {
                'total_evaluations': total_evaluations,
                'average_score': round(result[0]['avg_score'], 2),
                'average_keyword_match': round(result[0]['avg_keyword_match'], 2),
                'average_similarity': round(result[0]['avg_similarity'], 2)
            }
        else:
            stats = {
                'total_evaluations': 0,
                'average_score': 0,
                'average_keyword_match': 0,
                'average_similarity': 0
            }
        
        return jsonify(stats), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    """Get evaluation history"""
    try:
        limit = int(request.args.get('limit', 10))
        
        evaluations = list(evaluations_collection.find().sort('timestamp', -1).limit(limit))
        
        # Convert ObjectId to string
        for eval in evaluations:
            eval['_id'] = str(eval['_id'])
            if eval.get('timestamp'):
                eval['timestamp'] = eval['timestamp'].isoformat()
        
        return jsonify(evaluations), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-history', methods=['DELETE'])
def clear_history():
    """Clear all evaluation history"""
    try:
        result = evaluations_collection.delete_many({})
        return jsonify({
            'success': True,
            'deleted_count': result.deleted_count
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 AUTOMATED ASSIGNMENT EVALUATION SYSTEM")
    print("="*60)
    print("\n✅ System initialized successfully!")
    print("📊 MongoDB Status: Connected")
    print("🌐 Flask Server: Starting...")
    print("\n📍 Access the application at: http://localhost:5000")
    print("📍 API Endpoints:")
    print("   - POST /evaluate     - Evaluate assignment")
    print("   - GET  /api/stats    - Get statistics")
    print("   - GET  /api/history  - Get evaluation history")
    print("\n💡 Press CTRL+C to stop the server")
    print("="*60 + "\n")
    
    app.run(debug=True, host='localhost', port=5000)