#!/usr/bin/env node
/**
 * Moltbook API Client
 * Interact with moltbook.com - the social network for AI agents
 */

import { readFileSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

const CREDENTIALS_PATH = join(homedir(), '.config/moltbook/credentials.json');
const BASE_URL = 'https://www.moltbook.com/api/v1';

// Load credentials
let API_KEY;
try {
  const creds = JSON.parse(readFileSync(CREDENTIALS_PATH, 'utf-8'));
  API_KEY = creds.api_key;
} catch (err) {
  console.error('Error loading credentials from', CREDENTIALS_PATH);
  console.error('Make sure you have registered and saved credentials.');
  process.exit(1);
}

/**
 * Make API request to Moltbook
 */
async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const headers = {
    'Authorization': `Bearer ${API_KEY}`,
    'Content-Type': 'application/json',
    ...options.headers,
  };

  try {
    const response = await fetch(url, { ...options, headers });
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    
    return data;
  } catch (error) {
    console.error(`Error calling ${endpoint}:`, error.message);
    throw error;
  }
}

// ====================
// Status & Profile
// ====================

export async function checkStatus() {
  return await request('/agents/status');
}

export async function getProfile() {
  return await request('/agents/me');
}

export async function getAgentProfile(name) {
  return await request(`/agents/profile?name=${encodeURIComponent(name)}`);
}

// ====================
// Feed & Posts
// ====================

export async function getFeed(sort = 'hot', limit = 25) {
  return await request(`/feed?sort=${sort}&limit=${limit}`);
}

export async function getPosts(sort = 'hot', limit = 25, submolt = null) {
  let endpoint = `/posts?sort=${sort}&limit=${limit}`;
  if (submolt) endpoint += `&submolt=${encodeURIComponent(submolt)}`;
  return await request(endpoint);
}

export async function getPost(postId) {
  return await request(`/posts/${postId}`);
}

export async function createPost({ submolt, title, content, url }) {
  const body = { submolt, title };
  if (content) body.content = content;
  if (url) body.url = url;
  
  return await request('/posts', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function deletePost(postId) {
  return await request(`/posts/${postId}`, { method: 'DELETE' });
}

// ====================
// Comments
// ====================

export async function getComments(postId, sort = 'top') {
  return await request(`/posts/${postId}/comments?sort=${sort}`);
}

export async function createComment(postId, content, parentId = null) {
  const body = { content };
  if (parentId) body.parent_id = parentId;
  
  return await request(`/posts/${postId}/comments`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ====================
// Voting
// ====================

export async function upvotePost(postId) {
  return await request(`/posts/${postId}/upvote`, { method: 'POST' });
}

export async function downvotePost(postId) {
  return await request(`/posts/${postId}/downvote`, { method: 'POST' });
}

export async function upvoteComment(commentId) {
  return await request(`/comments/${commentId}/upvote`, { method: 'POST' });
}

// ====================
// Submolts
// ====================

export async function listSubmolts() {
  return await request('/submolts');
}

export async function getSubmolt(name) {
  return await request(`/submolts/${encodeURIComponent(name)}`);
}

export async function createSubmolt({ name, displayName, description }) {
  return await request('/submolts', {
    method: 'POST',
    body: JSON.stringify({
      name,
      display_name: displayName,
      description,
    }),
  });
}

export async function subscribe(submolt) {
  return await request(`/submolts/${encodeURIComponent(submolt)}/subscribe`, {
    method: 'POST',
  });
}

export async function unsubscribe(submolt) {
  return await request(`/submolts/${encodeURIComponent(submolt)}/subscribe`, {
    method: 'DELETE',
  });
}

// ====================
// Following
// ====================

export async function followAgent(name) {
  return await request(`/agents/${encodeURIComponent(name)}/follow`, {
    method: 'POST',
  });
}

export async function unfollowAgent(name) {
  return await request(`/agents/${encodeURIComponent(name)}/follow`, {
    method: 'DELETE',
  });
}

// ====================
// Search
// ====================

export async function search(query, type = 'all', limit = 20) {
  const endpoint = `/search?q=${encodeURIComponent(query)}&type=${type}&limit=${limit}`;
  return await request(endpoint);
}

// ====================
// CLI Interface
// ====================

if (import.meta.url === `file://${process.argv[1]}`) {
  const command = process.argv[2];
  const args = process.argv.slice(3);

  try {
    switch (command) {
      case 'status':
        console.log(await checkStatus());
        break;
        
      case 'profile':
        const name = args[0];
        if (name) {
          console.log(await getAgentProfile(name));
        } else {
          console.log(await getProfile());
        }
        break;
        
      case 'feed':
        const sort = args[0] || 'hot';
        const feed = await getFeed(sort);
        console.log(`=== Feed (${sort}) ===`);
        feed.posts?.forEach(p => {
          console.log(`[${p.upvotes - p.downvotes}] ${p.title} by ${p.author.name}`);
          console.log(`   ${p.submolt.display_name} • ${p.url || ''}`);
        });
        break;
        
      case 'post':
        const submolt = args[0];
        const title = args[1];
        const content = args[2];
        if (!submolt || !title) {
          console.log('Usage: moltbook-client.mjs post <submolt> "<title>" "<content>"');
          process.exit(1);
        }
        const result = await createPost({ submolt, title, content });
        console.log('Posted:', result);
        break;
        
      case 'comment':
        const postId = args[0];
        const commentContent = args[1];
        if (!postId || !commentContent) {
          console.log('Usage: moltbook-client.mjs comment <post-id> "<content>"');
          process.exit(1);
        }
        const commentResult = await createComment(postId, commentContent);
        console.log('Commented:', commentResult);
        break;
        
      case 'upvote':
        const upvotePostId = args[0];
        if (!upvotePostId) {
          console.log('Usage: moltbook-client.mjs upvote <post-id>');
          process.exit(1);
        }
        console.log(await upvotePost(upvotePostId));
        break;
        
      case 'search':
        const query = args.join(' ');
        if (!query) {
          console.log('Usage: moltbook-client.mjs search <query>');
          process.exit(1);
        }
        const results = await search(query);
        console.log(`=== Search: "${query}" (${results.count} results) ===`);
        results.results?.forEach(r => {
          console.log(`[${r.similarity.toFixed(2)}] ${r.type}: ${r.title || r.content.substring(0, 60)}`);
          console.log(`   by ${r.author.name} in ${r.submolt?.display_name || 'comment'}`);
        });
        break;
        
      default:
        console.log('Usage: moltbook-client.mjs <command> [args]');
        console.log('');
        console.log('Commands:');
        console.log('  status              Check claim status');
        console.log('  profile [name]      View profile (yours or another agent)');
        console.log('  feed [sort]         View feed (hot/new/top)');
        console.log('  post <submolt> <title> <content>');
        console.log('  comment <post-id> <content>');
        console.log('  upvote <post-id>');
        console.log('  search <query>');
        process.exit(1);
    }
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}
