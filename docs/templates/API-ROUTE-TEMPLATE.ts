// API Route Template for Mission Control
// File: app/api/[route-name]/route.ts

import { NextRequest, NextResponse } from 'next/server';
import { readFileSync } from 'fs';
import { join } from 'path';

// Force dynamic rendering (no static optimization)
export const dynamic = 'force-dynamic';

/**
 * GET /api/[route-name]
 * 
 * Description: Brief description of what this endpoint does
 * 
 * @returns JSON response with data or error
 */
export async function GET(request: NextRequest) {
  try {
    // 1. Parse query parameters (if needed)
    const { searchParams } = new URL(request.url);
    const param = searchParams.get('param');

    // 2. Validate input
    if (param && typeof param !== 'string') {
      return NextResponse.json(
        { error: 'Invalid parameter type' },
        { status: 400 }
      );
    }

    // 3. Read data from file system
    const dataPath = join(process.cwd(), 'trading', 'logs', 'data.json');
    
    let data;
    try {
      const fileContent = readFileSync(dataPath, 'utf-8');
      data = JSON.parse(fileContent);
    } catch (fileError) {
      console.error('Error reading data file:', fileError);
      return NextResponse.json(
        { 
          error: 'Data file not found',
          details: 'Make sure the data aggregator is running'
        },
        { status: 404 }
      );
    }

    // 4. Process data (if needed)
    const processedData = processData(data, param);

    // 5. Return response
    return NextResponse.json(processedData, {
      headers: {
        'Cache-Control': 'no-store, max-age=0',
      },
    });

  } catch (error) {
    console.error('Error in API route:', error);
    return NextResponse.json(
      { 
        error: 'Internal server error',
        message: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

/**
 * POST /api/[route-name]
 * 
 * Description: Brief description of what this endpoint does
 * 
 * @param request - Request with JSON body
 * @returns JSON response with result or error
 */
export async function POST(request: NextRequest) {
  try {
    // 1. Parse request body
    const body = await request.json();

    // 2. Validate input with type guard
    if (!isValidRequestBody(body)) {
      return NextResponse.json(
        { error: 'Invalid request body' },
        { status: 400 }
      );
    }

    // 3. Process request
    const result = await processRequest(body);

    // 4. Return response
    return NextResponse.json(result);

  } catch (error) {
    console.error('Error in POST route:', error);
    return NextResponse.json(
      { 
        error: 'Internal server error',
        message: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

// Helper functions

/**
 * Type guard for request body validation
 */
function isValidRequestBody(body: unknown): body is RequestBody {
  return (
    typeof body === 'object' &&
    body !== null &&
    'field' in body &&
    typeof (body as RequestBody).field === 'string'
  );
}

interface RequestBody {
  field: string;
  // Add other fields
}

/**
 * Process data based on parameters
 */
function processData(data: unknown, param: string | null): ProcessedData {
  // Type guard
  if (!isValidData(data)) {
    throw new Error('Invalid data format');
  }

  // Process and return
  return {
    timestamp: new Date().toISOString(),
    data: data,
    param: param,
  };
}

function isValidData(data: unknown): data is DataType {
  return (
    typeof data === 'object' &&
    data !== null &&
    'field' in data
  );
}

interface DataType {
  field: string;
  // Add other fields
}

interface ProcessedData {
  timestamp: string;
  data: DataType;
  param: string | null;
}

async function processRequest(body: RequestBody): Promise<{ success: boolean }> {
  // Implementation
  return { success: true };
}

// Quality Gates Checklist:
// [ ] Type guards for all external data
// [ ] Error handling with try-catch
// [ ] Helpful error messages
// [ ] No console.log (console.error in catch is OK)
// [ ] dynamic = 'force-dynamic' for real-time data
// [ ] Cache-Control headers set appropriately
// [ ] Input validation
// [ ] Proper HTTP status codes (200, 400, 404, 500)
