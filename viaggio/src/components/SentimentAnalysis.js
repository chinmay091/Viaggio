import React, { useState } from 'react';
import Sentiment from 'sentiment';


import '../components/frontend/style.css';

const SentimentAnalysis = () => {
  const [reviews, setReviews] = useState('');
  const [sentimentResult, setSentimentResult] = useState(null);

  const analyzeSentiment = () => {
    const sentiment = new Sentiment();
    const analysis = sentiment.analyze(reviews);
    setSentimentResult(analysis);
  };

  // const renderStars = (score) => {
  //   const starCount = Math.round((score + 5) / 10) * 5;
  //   return '⭐'.repeat(starCount);
  // };

  const renderStars = (score) => {
    const starCount = Math.min(Math.max(Math.round((score / 10) * 5), 0), 5);
    return '⭐'.repeat(starCount);
  };
  

  return (
    <div>
      <textarea id='textbutton'
        value={reviews}
        onChange={(e) => setReviews(e.target.value)}
        rows="2"
        cols="50"
        placeholder="Enter Reviews..."
      />
      <br></br>
      <button onClick={analyzeSentiment} id='sentimentbutton' >Submit</button>
      {sentimentResult && (
        <div>
          {/* <p>Score: {sentimentResult.score}</p>
          <p>Sentiment: {sentimentResult.score > 0 ? 'Positive' : sentimentResult.score < 0 ? 'Negative' : 'Neutral'}</p> */}
          <p>Thank You for Reviewing!!! {renderStars(sentimentResult.score)}</p>
        </div>
      )}
    </div>
  );
};

export default SentimentAnalysis;
