import http from 'k6/http';

export const options = {
  vus: 150,     
  duration: '30s',
};

export default function () {
  http.get('http://localhost:80/');
  // pas de sleep : envoie en continu, sans pause
}