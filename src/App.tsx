import React, { useState, useEffect, useRef } from 'react';
import { 
  TrendingUp, Calendar, Edit3, Settings, Play, 
  HelpCircle, User, Award, List, CheckCircle2, XCircle, Search, RefreshCw
} from 'lucide-react';
import { 
  dbInstance, 
  loadAllQuestions, 
  saveUserAnswer, 
  updateUserAnswer, 
  getQuestionAnswersHistory, 
  type Question, 
  type UserAnswer 
} from './data/db';

declare global {
  interface Window {
    electronAPI: {
      loginToLL: (username: string, password: string) => Promise<{ success: boolean; profileId?: string; username?: string; error?: string }>;
      fetchLL: (url: string) => Promise<{ success: boolean; data?: string; error?: string }>;
    };
  }
}

const CATEGORIES = [
  "ALL",
  "AMER HIST",
  "ART",
  "BUS/ECON",
  "CLASS MUSIC",
  "CURR EVENTS",
  "FILM",
  "FOOD/DRINK",
  "GAMES/SPORT",
  "GEOGRAPHY",
  "LANGUAGE",
  "LIFESTYLE",
  "LITERATURE",
  "MATH",
  "POP MUSIC",
  "SCIENCE",
  "TELEVISION",
  "THEATRE",
  "WORLD HIST"
];

const App: React.FC = () => {
const directLoginToLL = async (username: string, password: string): Promise<{ success: boolean; profileId?: string; username?: string; error?: string }> => {
  try {
    const postData = new URLSearchParams({
      login: "Login",
      username: username,
      password: password
    });
    
    await fetch("https://www.learnedleague.com/ucp.php?mode=login", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded"
      },
      body: postData
    });
    
    const testRes = await fetch("https://www.learnedleague.com");
    const html = await testRes.text();
    const hasFlag = html.includes("class=\"flag\"");
    const hasIncorrect = html.includes("incorrect") || html.includes("Incorrect");
    
    if (hasFlag && !hasIncorrect) {
      const profileMatch = html.match(/profiles\.php\?(\d+)/);
      const profileId = profileMatch ? profileMatch[1] : "";
      return { success: true, profileId, username };
    } else {
      return { success: false, error: "Invalid username/password or Cloudflare challenge. Open LL website in browser to solve." };
    }
  } catch (err: any) {
    return { success: false, error: err.message };
  }
};

const directFetchLL = async (url: string): Promise<{ success: boolean; data?: string; error?: string }> => {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      return { success: false, error: `HTTP ${response.status}` };
    }
    const data = await response.text();
    return { success: true, data };
  } catch (err: any) {
    return { success: false, error: err.message };
  }
};

  // Navigation State
  const [currentPage, setCurrentPage] = useState<'practice' | 'mockday' | 'onedays' | 'minileagues' | 'settings'>('practice');
  const [isLoading, setIsLoading] = useState(true);
  
  // Database state
  const [allQuestions, setAllQuestions] = useState<Question[]>([]);
  const [filteredQuestions, setFilteredQuestions] = useState<Question[]>([]);
  
  // Practice Filter States
  const [selectedSeason, setSelectedSeason] = useState<string>('ALL');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [minPercent, setMinPercent] = useState<number>(0);
  const [maxPercent, setMaxPercent] = useState<number>(100);
  const [searchQuery, setSearchQuery] = useState<string>('');
  
  // Current question states
  const [currentIdx, setCurrentIdx] = useState<number>(0);
  const [userSubmission, setUserSubmission] = useState<string>('');
  const [showAnswer, setShowAnswer] = useState<boolean>(false);
  const [lastSavedAnswer, setLastSavedAnswer] = useState<UserAnswer | null>(null);
  const [submitFeedback, setSubmitFeedback] = useState<{ submitted: boolean; correct: boolean } | null>(null);

  // Mock Match Day States
  const [mockThreshold, setMockThreshold] = useState<number>(0);
  const [mockSeed, setMockSeed] = useState<string>('');
  const [mockQuestions, setMockQuestions] = useState<Question[]>([]);
  const [mockSubmissions, setMockSubmissions] = useState<string[]>(['', '', '', '', '', '']);
  const [mockRevealed, setMockRevealed] = useState<boolean[]>([false, false, false, false, false, false]);
  const [mockFeedback, setMockFeedback] = useState<{ submitted: boolean; correct: boolean }[]>([
    { submitted: false, correct: false },
    { submitted: false, correct: false },
    { submitted: false, correct: false },
    { submitted: false, correct: false },
    { submitted: false, correct: false },
    { submitted: false, correct: false }
  ]);

  // One Day Specials States
  const [oneDaysList, setOneDaysList] = useState<{ title: string; url: string; date: string }[]>([]);
  const [oneDaysLoading, setOneDaysLoading] = useState<boolean>(false);
  const [selectedOneDay, setSelectedOneDay] = useState<any>(null);
  const [oneDaySearchQuery, setOneDaySearchQuery] = useState<string>('');
  const [oneDayAnswers, setOneDayAnswers] = useState<string[]>([]);
  const [oneDayRevealed, setOneDayRevealed] = useState<boolean[]>([]);

  // Mini Leagues States
  const [miniLeaguesList, setMiniLeaguesList] = useState<{ title: string; url: string; date: string; number_of_players: string }[]>([]);
  const [miniLeaguesLoading, setMiniLeaguesLoading] = useState<boolean>(false);
  const [selectedMiniLeague, setSelectedMiniLeague] = useState<any>(null);
  const [miniAnswers, setMiniAnswers] = useState<Record<string, string>>({}); // maps question key to submission
  const [miniRevealed, setMiniRevealed] = useState<Record<string, boolean>>({}); // maps question key to show/hide

  // Settings / Account States
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [profileId, setProfileId] = useState<string>('');
  const [loginStatus, setLoginStatus] = useState<string>('');
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(false);

  // Load database on mount
  useEffect(() => {
    loadAllQuestions()
      .then((qs) => {
        setAllQuestions(qs);
        setFilteredQuestions(qs);
        setIsLoading(false);
        
        // Pick a random question to start
        if (qs.length > 0) {
          const rand = Math.floor(Math.random() * qs.length);
          setCurrentIdx(rand);
        }
      })
      .catch((err) => {
        console.error("Database initialization failed", err);
        setIsLoading(false);
      });

    // Check settings for login credentials
    dbInstance.settings.toArray().then((settings) => {
      const u = settings.find(s => s.key === 'username')?.value || '';
      const p = settings.find(s => s.key === 'password')?.value || '';
      const pid = settings.find(s => s.key === 'profileId')?.value || '';
      
      if (u) setUsername(u);
      if (p) setPassword(p);
      if (pid) {
        setProfileId(pid);
        setIsLoggedIn(true);
      }
    });
  }, []);

  // Update filtered questions list whenever filter state changes
  useEffect(() => {
    if (allQuestions.length === 0) return;

    let filtered = allQuestions;

    if (selectedSeason !== 'ALL') {
      filtered = filtered.filter(q => q.season === parseInt(selectedSeason));
    }
    if (selectedCategory !== 'ALL') {
      filtered = filtered.filter(q => q.category.toUpperCase() === selectedCategory.toUpperCase());
    }
    
    // Difficulty filters
    filtered = filtered.filter(q => {
      const pct = parseFloat(q.percent);
      if (isNaN(pct)) return true;
      return pct >= minPercent && pct <= maxPercent;
    });

    // Search query filter
    if (searchQuery.trim() !== '') {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(q => 
        q.question.toLowerCase().includes(query) || 
        q.answer.toLowerCase().includes(query) ||
        q.category.toLowerCase().includes(query)
      );
    }

    setFilteredQuestions(filtered);
    setCurrentIdx(0);
  }, [selectedSeason, selectedCategory, minPercent, maxPercent, searchQuery, allQuestions]);

  // Load history when current question changes
  useEffect(() => {
    if (filteredQuestions.length === 0 || currentIdx >= filteredQuestions.length) {
      setSubmitFeedback(null);
      setLastSavedAnswer(null);
      return;
    }
    const currentQ = filteredQuestions[currentIdx];
    getQuestionAnswersHistory(currentQ.id).then((history) => {
      if (history.length > 0) {
        const last = history[history.length - 1];
        setLastSavedAnswer(last);
        setSubmitFeedback({
          submitted: true,
          correct: last.correct === 1
        });
        setUserSubmission(last.submitted_answer);
        setShowAnswer(true);
      } else {
        setLastSavedAnswer(null);
        setSubmitFeedback(null);
        setUserSubmission('');
        setShowAnswer(false);
      }
    });
  }, [currentIdx, filteredQuestions]);

  // Fetch OneDays list
  const handleLoadOneDays = async () => {
    setOneDaysLoading(true);
    try {
      const res = await directFetchLL("https://www.learnedleague.com/oneday/onedaysalpha.php");
      if (res.success && res.data) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(res.data, 'text/html');
        const rows = doc.querySelectorAll('table.std.min tbody tr');
        const parsedList: any[] = [];
        
        rows.forEach((row, index) => {
          if (index === 0) return; // Header
          const tdTitle = row.querySelector('td.std-left');
          const tdDate = row.querySelector('td.std-midleft');
          if (tdTitle && tdDate) {
            const title = tdTitle.textContent?.trim() || "";
            const link = tdTitle.querySelector('a')?.getAttribute('href') || "";
            const date = tdDate.textContent?.trim() || "";
            if (title && link) {
              parsedList.push({
                title,
                url: "https://www.learnedleague.com" + link,
                date
              });
            }
          }
        });
        
        setOneDaysList(parsedList);
      } else {
        alert("Failed to load OneDays: Access Forbidden (403). Make sure you are logged in under Settings.");
      }
    } catch (e) {
      console.error(e);
      alert("Error loading OneDays: " + e);
    }
    setOneDaysLoading(false);
  };

  // Load specific OneDay details
  const handleSelectOneDay = async (onedayItem: any) => {
    setOneDaysLoading(true);
    try {
      const pageRes = await directFetchLL(onedayItem.url);
      if (pageRes.success && pageRes.data) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(pageRes.data, 'text/html');
        
        // Parse tabs for metrics links
        let metricsUrl = "";
        const profileTab = doc.querySelector('ul#profilestabs a');
        if (profileTab) {
          metricsUrl = "https://www.learnedleague.com" + profileTab.getAttribute('href');
        }
        
        // Parse blurb description
        const blurbEl = doc.querySelector('div.blurb');
        const blurb = blurbEl ? blurbEl.textContent?.trim() : "No description available.";

        // Parse questions & answers
        const questionParas = doc.querySelectorAll('div#qs_close.qdivshow_wide p');
        const answerDivs = doc.querySelectorAll('div#qs_close.qdivshow_wide div.answer3');
        
        const qTexts: string[] = [];
        questionParas.forEach(p => {
          // Strip out leading numbers
          const cleanText = p.textContent?.replace(/^\d+\.\s*/, '').trim() || "";
          if (cleanText) qTexts.push(cleanText);
        });

        const ansTexts: string[] = [];
        answerDivs.forEach(div => {
          const cleanAns = div.textContent?.split('\n').pop()?.trim() || "";
          ansTexts.push(cleanAns);
        });

        // Load metrics if available
        let difficulty = "N/A";
        let overallAvg = "N/A";
        let playerNum = "N/A";
        if (metricsUrl) {
          const metricsRes = await directFetchLL(metricsUrl);
          if (metricsRes.success && metricsRes.data) {
            const mDoc = parser.parseFromString(metricsRes.data, 'text/html');
            // Extract difficulty/metrics
            const statCells = mDoc.querySelectorAll('table.std tbody tr td');
            if (statCells.length > 5) {
              overallAvg = statCells[0].textContent?.trim() || "N/A";
              difficulty = statCells[1].textContent?.trim() || "N/A";
              playerNum = statCells[4].textContent?.trim() || "N/A";
            }
          }
        }

        const dataQuestions = qTexts.map((q, idx) => ({
          question: q,
          answer: ansTexts[idx] || ""
        }));

        setSelectedOneDay({
          title: onedayItem.title,
          date: onedayItem.date,
          blurb,
          difficulty_rating: difficulty,
          overall_average: overallAvg,
          number_of_players: playerNum,
          questions: dataQuestions
        });

        setOneDayAnswers(new Array(dataQuestions.length).fill(''));
        setOneDayRevealed(new Array(dataQuestions.length).fill(false));
      }
    } catch (e) {
      alert("Error loading OneDay details: " + e);
    }
    setOneDaysLoading(false);
  };

  // Fetch MiniLeagues List
  const handleLoadMiniLeagues = async () => {
    setMiniLeaguesLoading(true);
    try {
      const res = await directFetchLL("https://www.learnedleague.com/mini/");
      if (res.success && res.data) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(res.data, 'text/html');
        const rows = doc.querySelectorAll('table.std.min tbody tr');
        const parsedList: any[] = [];
        
        rows.forEach((row, idx) => {
          if (idx < 3) return; // Headers and spacing
          const tdTitle = row.querySelector('td.std-left');
          const tdDate = row.querySelector('td.std-midleft');
          const tdPlayers = row.querySelector('td.std-mid');
          if (tdTitle && tdDate) {
            const title = tdTitle.textContent?.trim() || "";
            const link = tdTitle.querySelector('a')?.getAttribute('href') || "";
            const date = tdDate.textContent?.trim() || "";
            const players = tdPlayers ? tdPlayers.textContent?.trim() : "N/A";
            if (title && link) {
              parsedList.push({
                title,
                url: "https://www.learnedleague.com" + link,
                date,
                number_of_players: players
              });
            }
          }
        });
        setMiniLeaguesList(parsedList);
      } else {
        alert("Failed to load Mini Leagues: Access Forbidden (403). Make sure you are logged in under Settings.");
      }
    } catch (e) {
      alert("Error loading Mini Leagues: " + e);
    }
    setMiniLeaguesLoading(false);
  };

  // Load specific MiniLeague details
  const handleSelectMiniLeague = async (miniItem: any) => {
    setMiniLeaguesLoading(true);
    try {
      const res = await directFetchLL(miniItem.url);
      if (res.success && res.data) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(res.data, 'text/html');
        
        // Find match days list
        const matchRows = doc.querySelectorAll('table.mtch tr');
        const matches: { title: string; url: string }[] = [];
        
        matchRows.forEach(row => {
          const a = row.querySelector('a');
          if (a) {
            matches.push({
              title: row.textContent?.trim() || "",
              url: "https://www.learnedleague.com" + a.getAttribute('href')
            });
          }
        });

        // Scraping each match page questions (up to 12 match days, 6 questions each)
        const matchDaysData: Record<string, { q: string; a: string; key: string }[]> = {};
        
        // Loop through matches and load questions synchronously (or in parallel)
        // To be fast and friendly, load first 3 match days to verify, or all
        for (let idx = 0; idx < Math.min(matches.length, 12); idx++) {
          const match = matches[idx];
          const mRes = await directFetchLL(match.url);
          if (mRes.success && mRes.data) {
            const mDoc = parser.parseFromString(mRes.data, 'text/html');
            const qEls = mDoc.querySelectorAll('div.ind-Q20');
            const aEls = mDoc.querySelectorAll('div.a-red');
            
            const list: any[] = [];
            for (let j = 0; j < qEls.length; j++) {
              const qText = qEls[j].textContent?.trim() || "";
              const aText = aEls[j] ? aEls[j].textContent?.trim() : "";
              list.push({
                q: qText,
                a: aText,
                key: `D${idx+1}Q${j+1}`
              });
            }
            matchDaysData[`Day ${idx+1}`] = list;
          }
        }

        setSelectedMiniLeague({
          title: miniItem.title,
          date: miniItem.date,
          number_of_players: miniItem.number_of_players,
          matchDays: matchDaysData
        });
        
        setMiniAnswers({});
        setMiniRevealed({});
      }
    } catch (e) {
      alert("Error loading MiniLeague details: " + e);
    }
    setMiniLeaguesLoading(false);
  };

  // Submit Answer to Practice Question
  const handleSubmitPractice = () => {
    if (filteredQuestions.length === 0) return;
    const currentQ = filteredQuestions[currentIdx];
    
    // Normalize and compare
    const isCorrect = userSubmission.toLowerCase().trim() === currentQ.answer.toLowerCase().trim();
    
    const ansObj: UserAnswer = {
      question_id: currentQ.id,
      submitted_answer: userSubmission,
      date: new Date().toISOString(),
      correct: isCorrect ? 1 : 0,
      override: 0
    };
    
    saveUserAnswer(ansObj).then((id) => {
      setLastSavedAnswer({ ...ansObj, id });
      setSubmitFeedback({
        submitted: true,
        correct: isCorrect
      });
      setShowAnswer(true);
    });
  };

  // Toggle Override
  const handleToggleOverride = () => {
    if (!lastSavedAnswer || !lastSavedAnswer.id) return;
    const newCorrect = !submitFeedback?.correct;
    
    updateUserAnswer(lastSavedAnswer.id, newCorrect).then(() => {
      setSubmitFeedback({
        submitted: true,
        correct: newCorrect
      });
    });
  };

  // Submit credentials to Learned League
  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setLoginStatus("Please fill in both fields.");
      return;
    }
    
    setLoginStatus("Authenticating...");
    try {
      const res = await directLoginToLL(username.trim(), password.trim());
      if (res.success && res.profileId) {
        setProfileId(res.profileId);
        setIsLoggedIn(true);
        setLoginStatus("Login Successful!");
        
        // Save to Dexie settings
        await dbInstance.settings.put({ key: 'username', value: username.trim() });
        await dbInstance.settings.put({ key: 'password', value: password.trim() });
        await dbInstance.settings.put({ key: 'profileId', value: res.profileId });
      } else {
        setIsLoggedIn(false);
        setLoginStatus(res.error || "Authentication failed.");
      }
    } catch (err: any) {
      setLoginStatus("Login Error: " + err.message);
    }
  };

  // Logout
  const handleLogout = async () => {
    setIsLoggedIn(false);
    setProfileId('');
    setUsername('');
    setPassword('');
    setLoginStatus("Logged Out.");
    
    await dbInstance.settings.delete('username');
    await dbInstance.settings.delete('password');
    await dbInstance.settings.delete('profileId');
  };

  // Mock Day Generation
  const handleGenerateMockDay = () => {
    // filter questions based on threshold
    let eligible = allQuestions.filter(q => {
      const pct = parseFloat(q.percent);
      return !isNaN(pct) && pct >= mockThreshold;
    });

    if (eligible.length < 6) {
      alert("Not enough questions matching the difficulty threshold! Try decreasing the threshold.");
      return;
    }

    // shuffle
    let shuffled = [...eligible];
    shuffled.sort(() => Math.random() - 0.5);

    // Pick 6
    const selected = shuffled.slice(0, 6);
    setMockQuestions(selected);
    setMockSubmissions(['', '', '', '', '', '']);
    setMockRevealed([false, false, false, false, false, false]);
    setMockFeedback(new Array(6).fill({ submitted: false, correct: false }));
  };

  // Submit Answer to a mock question
  const handleSubmitMockAnswer = (idx: number) => {
    const q = mockQuestions[idx];
    const sub = mockSubmissions[idx];
    const isCorrect = sub.toLowerCase().trim() === q.answer.toLowerCase().trim();
    
    const newFeedback = [...mockFeedback];
    newFeedback[idx] = { submitted: true, correct: isCorrect };
    setMockFeedback(newFeedback);

    const newRevealed = [...mockRevealed];
    newRevealed[idx] = true;
    setMockRevealed(newRevealed);
  };

  const getMockScore = () => {
    return mockFeedback.reduce((acc, curr) => acc + (curr.submitted && curr.correct ? 1 : 0), 0);
  };

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="logo-container">
          <Award className="logo-icon" size={32} />
          <span className="logo-text">LearnedLeague</span>
        </div>
        
        <ul className="nav-list">
          <li 
            className={`nav-item ${currentPage === 'practice' ? 'active' : ''}`}
            onClick={() => setCurrentPage('practice')}
          >
            <HelpCircle size={20} />
            <span>Practice Qs</span>
          </li>
          <li 
            className={`nav-item ${currentPage === 'mockday' ? 'active' : ''}`}
            onClick={() => setCurrentPage('mockday')}
          >
            <Play size={20} />
            <span>Mock Match Day</span>
          </li>
          <li 
            className={`nav-item ${currentPage === 'onedays' ? 'active' : ''}`}
            onClick={() => setCurrentPage('onedays')}
          >
            <Calendar size={20} />
            <span>OneDay Specials</span>
          </li>
          <li 
            className={`nav-item ${currentPage === 'minileagues' ? 'active' : ''}`}
            onClick={() => setCurrentPage('minileagues')}
          >
            <List size={20} />
            <span>Mini Leagues</span>
          </li>
          <li 
            className={`nav-item ${currentPage === 'settings' ? 'active' : ''}`}
            onClick={() => setCurrentPage('settings')}
          >
            <Settings size={20} />
            <span>Settings / Login</span>
          </li>
        </ul>

        <div className="sidebar-footer">
          <p className="sidebar-footer-text">
            {isLoggedIn ? `Logged in as ${username}` : "Offline / Not Logged In"}
          </p>
        </div>
      </aside>

      {/* Main Panel Content */}
      <main className="main-content">
        {isLoading ? (
          <div className="spinner-container">
            <div className="spinner"></div>
            <p>Initializing LearnedLeague Database...</p>
          </div>
        ) : (
          <>
            {/* 1. Practice Panel */}
            {currentPage === 'practice' && (
              <div className="practice-container">
                <header className="page-header">
                  <div className="page-title-group">
                    <h1>Question Practice</h1>
                    <p>Practice with past LearnedLeague seasons</p>
                  </div>
                </header>

                {/* Filters */}
                <div className="glass-panel form-row">
                  <div className="form-group">
                    <label>Season</label>
                    <select 
                      className="select-input"
                      value={selectedSeason}
                      onChange={(e) => setSelectedSeason(e.target.value)}
                    >
                      <option value="ALL">All Seasons</option>
                      {/* Generates seasons 60 to latest in DB */}
                      {Array.from(new Set(allQuestions.map(q => q.season)))
                        .sort((a,b) => b-a)
                        .map(s => (
                          <option key={s} value={s}>Season {s}</option>
                        ))
                      }
                    </select>
                  </div>

                  <div className="form-group">
                    <label>Category</label>
                    <select 
                      className="select-input"
                      value={selectedCategory}
                      onChange={(e) => setSelectedCategory(e.target.value)}
                    >
                      {CATEGORIES.map(c => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label>Min % Correct</label>
                    <input 
                      type="number" 
                      className="text-input"
                      value={minPercent} 
                      onChange={(e) => setMinPercent(parseInt(e.target.value) || 0)}
                      min="0" max="100" 
                    />
                  </div>

                  <div className="form-group">
                    <label>Max % Correct</label>
                    <input 
                      type="number" 
                      className="text-input"
                      value={maxPercent} 
                      onChange={(e) => setMaxPercent(parseInt(e.target.value) || 100)}
                      min="0" max="100" 
                    />
                  </div>

                  <div className="form-group" style={{ minWidth: '250px' }}>
                    <label>Search text</label>
                    <div style={{ position: 'relative' }}>
                      <input 
                        type="text" 
                        className="text-input" 
                        placeholder="Search Q/A..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                      />
                    </div>
                  </div>
                </div>

                {filteredQuestions.length === 0 ? (
                  <div className="glass-panel" style={{ textAlign: 'center', padding: '3rem' }}>
                    <p style={{ color: 'var(--text-muted)' }}>No questions match your current search parameters.</p>
                  </div>
                ) : (
                  <>
                    {/* Active Question Box */}
                    <div className="glass-panel question-panel">
                      <div className="question-meta-grid" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', flex: 1 }}>
                          <div className="question-meta-item" style={{ padding: '0.4rem 0.6rem', flex: '1', minWidth: '110px' }}>
                            <span className="question-meta-label" style={{ fontSize: '0.65rem' }}>Season / Day</span>
                            <span className="question-meta-value" style={{ fontSize: '0.85rem' }}>S{filteredQuestions[currentIdx].season} Day {filteredQuestions[currentIdx].question_num.substring(1,3)}</span>
                          </div>
                          <div className="question-meta-item" style={{ padding: '0.4rem 0.6rem', flex: '1', minWidth: '110px' }}>
                            <span className="question-meta-label" style={{ fontSize: '0.65rem' }}>Category</span>
                            <span className="question-meta-value" style={{ fontSize: '0.85rem' }}>{filteredQuestions[currentIdx].category}</span>
                          </div>
                          <div className="question-meta-item" style={{ padding: '0.4rem 0.6rem', flex: '1', minWidth: '110px' }}>
                            <span className="question-meta-label" style={{ fontSize: '0.65rem' }}>LL Difficulty</span>
                            <span className="question-meta-value" style={{ fontSize: '0.85rem' }}>{filteredQuestions[currentIdx].percent}% Correct</span>
                          </div>
                          <div className="question-meta-item" style={{ padding: '0.4rem 0.6rem', flex: '1', minWidth: '110px' }}>
                            <span className="question-meta-label" style={{ fontSize: '0.65rem' }}>Defense Value</span>
                            <span className="question-meta-value" style={{ fontSize: '0.85rem' }}>{filteredQuestions[currentIdx].defense}</span>
                          </div>
                        </div>

                        {/* Navigation Buttons Row */}
                        <div style={{ display: 'flex', gap: '0.35rem' }}>
                          <button 
                            className="btn" 
                            style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }}
                            disabled={currentIdx === 0}
                            onClick={() => setCurrentIdx(prev => prev - 1)}
                          >
                            Previous
                          </button>
                          <button 
                            className="btn" 
                            style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }}
                            onClick={() => setCurrentPage('practice')}
                          >
                            Reset
                          </button>
                          <button 
                            className="btn" 
                            style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }}
                            disabled={currentIdx === filteredQuestions.length - 1}
                            onClick={() => setCurrentIdx(prev => prev + 1)}
                          >
                            Next
                          </button>
                        </div>
                      </div>

                      <div className="question-text-box">
                        {filteredQuestions[currentIdx].question}
                      </div>

                      {/* Rundle Stats */}
                      <div className="table-wrapper" style={{ margin: 0 }}>
                        <table className="budget-table">
                          <thead>
                            <tr>
                              <th>Rundle A</th>
                              <th>Rundle B</th>
                              <th>Rundle C</th>
                              <th>Rundle D</th>
                              <th>Rundle E</th>
                              <th>Rookie (R)</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr>
                              <td>{filteredQuestions[currentIdx].A}%</td>
                              <td>{filteredQuestions[currentIdx].B}%</td>
                              <td>{filteredQuestions[currentIdx].C}%</td>
                              <td>{filteredQuestions[currentIdx].D}%</td>
                              <td>{filteredQuestions[currentIdx].E}%</td>
                              <td>{filteredQuestions[currentIdx].R}%</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>

                      {/* Answer Entry */}
                      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                        <input 
                          type="text" 
                          className="text-input" 
                          placeholder="Type your answer here..."
                          value={userSubmission}
                          onChange={(e) => {
                            setUserSubmission(e.target.value);
                          }}
                          onKeyDown={(e) => e.key === 'Enter' && handleSubmitPractice()}
                          disabled={showAnswer}
                        />
                        <button 
                          className="btn primary" 
                          onClick={handleSubmitPractice}
                          disabled={showAnswer || !userSubmission.trim()}
                        >
                          Submit
                        </button>
                      </div>

                      {/* Feedback Panel */}
                      {showAnswer && (
                        <div className={`answer-panel ${submitFeedback?.correct ? 'correct' : 'incorrect'}`}>
                          <div>
                            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>CORRECT ANSWER:</p>
                            <h3 style={{ fontSize: '1.25rem', fontFamily: 'var(--font-title)' }}>{filteredQuestions[currentIdx].answer}</h3>
                            
                            {submitFeedback && (
                              <p style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                {submitFeedback.correct ? (
                                  <><CheckCircle2 size={16} color="var(--accent-emerald)" /> Correct</>
                                ) : (
                                  <><XCircle size={16} color="var(--accent-rose)" /> Incorrect (Your answer: "{userSubmission}")</>
                                )}
                              </p>
                            )}
                          </div>

                          {submitFeedback && (
                            <label className="override-checkbox-label">
                              <input 
                                type="checkbox" 
                                className="override-checkbox"
                                checked={submitFeedback.correct} 
                                onChange={handleToggleOverride}
                              />
                              Override assessment
                            </label>
                          )}
                        </div>
                      )}

                      {/* Navigation bar */}
                      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1rem' }}>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button 
                            className="btn cyan"
                            onClick={() => setShowAnswer(prev => !prev)}
                          >
                            {showAnswer ? "Hide Answer" : "Reveal Answer"}
                          </button>
                          <button 
                            className="btn primary"
                            onClick={() => {
                              const rand = Math.floor(Math.random() * filteredQuestions.length);
                              setCurrentIdx(rand);
                            }}
                          >
                            <RefreshCw size={16} /> Random Question
                          </button>
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* 2. Mock Match Day */}
            {currentPage === 'mockday' && (
              <div>
                <header className="page-header">
                  <div className="page-title-group">
                    <h1>Mock Match Day</h1>
                    <p>Play 6 random questions in a simulated match day</p>
                  </div>
                </header>

                <div className="glass-panel form-row">
                  <div className="form-group">
                    <label>Min Difficulty Threshold (% Correct)</label>
                    <input 
                      type="number" 
                      className="text-input" 
                      value={mockThreshold}
                      onChange={(e) => setMockThreshold(parseInt(e.target.value) || 0)}
                      min="0" max="95"
                    />
                  </div>

                  <div className="form-group">
                    <label>Seed (Optional)</label>
                    <input 
                      type="text" 
                      className="text-input" 
                      placeholder="Random seed..."
                      value={mockSeed}
                      onChange={(e) => setMockSeed(e.target.value)}
                    />
                  </div>

                  <button className="btn primary" onClick={handleGenerateMockDay}>
                    Generate Match Day
                  </button>
                </div>

                {mockQuestions.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', marginTop: '2rem' }}>
                    <div className="glass-panel" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <h3 style={{ fontSize: '1.5rem' }}>Match Progress</h3>
                      <span style={{ fontSize: '1.25rem', color: 'var(--accent-cyan)', fontWeight: 'bold' }}>
                        Score: {getMockScore()} / 6
                      </span>
                    </div>

                    {mockQuestions.map((q, idx) => (
                      <div className="glass-panel" key={q.id}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: 'bold' }}>QUESTION {idx + 1} ({q.category}) - {q.percent}% Correct</span>
                        </div>
                        <p style={{ fontSize: '1.15rem', marginBottom: '1rem' }}>{q.question}</p>
                        
                        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
                          <input 
                            type="text" 
                            className="text-input" 
                            placeholder="Type answer..."
                            value={mockSubmissions[idx]}
                            onChange={(e) => {
                              const list = [...mockSubmissions];
                              list[idx] = e.target.value;
                              setMockSubmissions(list);
                            }}
                            disabled={mockFeedback[idx].submitted}
                          />
                          <button 
                            className="btn primary"
                            disabled={mockFeedback[idx].submitted || !mockSubmissions[idx].trim()}
                            onClick={() => handleSubmitMockAnswer(idx)}
                          >
                            Submit
                          </button>
                        </div>

                        {mockRevealed[idx] && (
                          <div className={`answer-panel ${mockFeedback[idx].correct ? 'correct' : 'incorrect'}`} style={{ margin: 0 }}>
                            <div>
                              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>CORRECT ANSWER:</p>
                              <h3>{q.answer}</h3>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* 3. One Day Specials */}
            {currentPage === 'onedays' && (
              <div>
                <header className="page-header">
                  <div className="page-title-group">
                    <h1>One Day Specials</h1>
                    <p>Load and practice specialized single-topic quizzes</p>
                  </div>
                </header>

                <div className="glass-panel form-row">
                  <button className="btn primary" onClick={handleLoadOneDays}>
                    Retrieve OneDays List
                  </button>
                  
                  {oneDaysList.length > 0 && (
                    <div className="form-group" style={{ minWidth: '300px' }}>
                      <input 
                        type="text" 
                        className="text-input" 
                        placeholder="Search quiz titles..."
                        value={oneDaySearchQuery}
                        onChange={(e) => setOneDaySearchQuery(e.target.value)}
                      />
                    </div>
                  )}
                </div>

                {oneDaysLoading ? (
                  <div className="spinner-container">
                    <div className="spinner"></div>
                    <p>Fetching One Day Specials Data...</p>
                  </div>
                ) : (
                  <div className="stats-grid" style={{ marginTop: '1.5rem' }}>
                    {/* Left: list of quizzes */}
                    {oneDaysList.length > 0 && (
                      <div className="glass-panel scroll-panel">
                        <h3 style={{ marginBottom: '1rem' }}>Available Quizzes</h3>
                        <div className="data-table-wrapper">
                          <table className="data-table">
                            <thead>
                              <tr>
                                <th>Date</th>
                                <th>Topic</th>
                              </tr>
                            </thead>
                            <tbody>
                              {oneDaysList
                                .filter(item => item.title.toLowerCase().includes(oneDaySearchQuery.toLowerCase()))
                                .map((item) => (
                                  <tr 
                                    key={item.url} 
                                    style={{ cursor: 'pointer' }}
                                    onClick={() => handleSelectOneDay(item)}
                                  >
                                    <td style={{ fontSize: '0.85rem' }}>{item.date}</td>
                                    <td style={{ fontWeight: '500' }}>{item.title}</td>
                                  </tr>
                                ))
                              }
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Right: details of selected quiz */}
                    {selectedOneDay ? (
                      <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        <div>
                          <h2 style={{ fontSize: '1.75rem', color: 'var(--accent-cyan)' }}>{selectedOneDay.title}</h2>
                          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Loaded date: {selectedOneDay.date}</p>
                        </div>

                        <div className="question-meta-grid">
                          <div className="question-meta-item">
                            <span className="question-meta-label">Difficulty</span>
                            <span className="question-meta-value">{selectedOneDay.difficulty_rating}</span>
                          </div>
                          <div className="question-meta-item">
                            <span className="question-meta-label">Avg Score</span>
                            <span className="question-meta-value">{selectedOneDay.overall_average}%</span>
                          </div>
                          <div className="question-meta-item">
                            <span className="question-meta-label">Players</span>
                            <span className="question-meta-value">{selectedOneDay.number_of_players}</span>
                          </div>
                        </div>

                        <div className="question-text-box" style={{ fontSize: '0.95rem', padding: '1rem' }}>
                          <p style={{ fontWeight: 'bold', marginBottom: '0.25rem', color: 'var(--accent-cyan)' }}>Description blurb:</p>
                          {selectedOneDay.blurb}
                        </div>

                        <div className="scroll-panel" style={{ maxHeight: '400px' }}>
                          {selectedOneDay.questions.map((q: any, idx: number) => (
                            <div key={idx} style={{ marginBottom: '1.5rem', borderBottom: '1px solid var(--card-border)', paddingBottom: '1rem' }}>
                              <p style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>Q{idx + 1}: {q.question}</p>
                              
                              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
                                <input 
                                  type="text" 
                                  className="text-input" 
                                  placeholder="Answer..."
                                  value={oneDayAnswers[idx]}
                                  onChange={(e) => {
                                    const list = [...oneDayAnswers];
                                    list[idx] = e.target.value;
                                    setOneDayAnswers(list);
                                  }}
                                  disabled={oneDayRevealed[idx]}
                                />
                                <button 
                                  className="btn primary"
                                  onClick={() => {
                                    const list = [...oneDayRevealed];
                                    list[idx] = true;
                                    setOneDayRevealed(list);
                                  }}
                                >
                                  Submit
                                </button>
                              </div>

                              {oneDayRevealed[idx] && (
                                <div className="answer-panel correct" style={{ margin: 0, padding: '0.5rem 1rem' }}>
                                  <p>Correct: <span style={{ fontWeight: 'bold' }}>{q.answer}</span></p>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      oneDaysList.length > 0 && (
                        <div className="glass-panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <p style={{ color: 'var(--text-muted)' }}>Select a One Day Special from the table to load its questions.</p>
                        </div>
                      )
                    )}
                  </div>
                )}
              </div>
            )}

            {/* 4. Mini Leagues */}
            {currentPage === 'minileagues' && (
              <div>
                <header className="page-header">
                  <div className="page-title-group">
                    <h1>Mini Leagues</h1>
                    <p>Load and practice past Mini-Leagues</p>
                  </div>
                </header>

                <div className="glass-panel form-row">
                  <button className="btn primary" onClick={handleLoadMiniLeagues}>
                    Retrieve MiniLeagues List
                  </button>
                </div>

                {miniLeaguesLoading ? (
                  <div className="spinner-container">
                    <div className="spinner"></div>
                    <p>Fetching Mini Leagues Data...</p>
                  </div>
                ) : (
                  <div className="stats-grid" style={{ marginTop: '1.5rem' }}>
                    {/* Left: list of MiniLeagues */}
                    {miniLeaguesList.length > 0 && (
                      <div className="glass-panel scroll-panel">
                        <h3 style={{ marginBottom: '1rem' }}>Available Mini Leagues</h3>
                        <div className="data-table-wrapper">
                          <table className="data-table">
                            <thead>
                              <tr>
                                <th>Date</th>
                                <th>Name</th>
                                <th>Players</th>
                              </tr>
                            </thead>
                            <tbody>
                              {miniLeaguesList.map((item) => (
                                <tr 
                                  key={item.url} 
                                  style={{ cursor: 'pointer' }}
                                  onClick={() => handleSelectMiniLeague(item)}
                                >
                                  <td style={{ fontSize: '0.85rem' }}>{item.date}</td>
                                  <td style={{ fontWeight: '500' }}>{item.title}</td>
                                  <td>{item.number_of_players}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Right: details of selected MiniLeague */}
                    {selectedMiniLeague ? (
                      <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        <div>
                          <h2 style={{ fontSize: '1.75rem', color: 'var(--accent-cyan)' }}>{selectedMiniLeague.title}</h2>
                          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Date: {selectedMiniLeague.date} | Players: {selectedMiniLeague.number_of_players}</p>
                        </div>

                        <div className="scroll-panel" style={{ maxHeight: '500px' }}>
                          {Object.keys(selectedMiniLeague.matchDays).map((dayKey) => (
                            <div key={dayKey} style={{ marginBottom: '2rem' }}>
                              <h3 style={{ borderBottom: '1px solid var(--card-border)', paddingBottom: '0.5rem', marginBottom: '1rem', color: 'var(--accent-cyan)' }}>{dayKey}</h3>
                              
                              {selectedMiniLeague.matchDays[dayKey].map((q: any) => {
                                const qKey = `${dayKey}-${q.key}`;
                                return (
                                  <div key={q.key} style={{ marginBottom: '1.5rem', paddingLeft: '0.5rem' }}>
                                    <p style={{ fontWeight: '500', marginBottom: '0.5rem' }}>{q.key}: {q.q}</p>
                                    
                                    <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
                                      <input 
                                        type="text" 
                                        className="text-input" 
                                        placeholder="Answer..."
                                        value={miniAnswers[qKey] || ''}
                                        onChange={(e) => {
                                          setMiniAnswers(prev => ({
                                            ...prev,
                                            [qKey]: e.target.value
                                          }));
                                        }}
                                        disabled={miniRevealed[qKey]}
                                      />
                                      <button 
                                        className="btn primary"
                                        onClick={() => {
                                          setMiniRevealed(prev => ({
                                            ...prev,
                                            [qKey]: true
                                          }));
                                        }}
                                      >
                                        Submit
                                      </button>
                                    </div>

                                    {miniRevealed[qKey] && (
                                      <div className="answer-panel correct" style={{ margin: 0, padding: '0.5rem 1rem' }}>
                                        <p>Correct: <span style={{ fontWeight: 'bold' }}>{q.a}</span></p>
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      miniLeaguesList.length > 0 && (
                        <div className="glass-panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <p style={{ color: 'var(--text-muted)' }}>Select a Mini League from the table to load its questions.</p>
                        </div>
                      )
                    )}
                  </div>
                )}
              </div>
            )}

            {/* 5. Settings / Login */}
            {currentPage === 'settings' && (
              <div>
                <header className="page-header">
                  <div className="page-title-group">
                    <h1>Settings & Accounts</h1>
                    <p>Configure LearnedLeague user authentication settings</p>
                  </div>
                </header>

                <div className="glass-panel" style={{ maxWidth: '600px', margin: '0 auto' }}>
                  <h3 style={{ marginBottom: '1.5rem', borderBottom: '1px solid var(--card-border)', paddingBottom: '0.5rem' }}>LearnedLeague.com Authentication</h3>
                  
                  <form onSubmit={handleLoginSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <div className="form-group">
                      <label>Username</label>
                      <input 
                        type="text" 
                        className="text-input" 
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        disabled={isLoggedIn}
                      />
                    </div>

                    <div className="form-group">
                      <label>Password</label>
                      <input 
                        type="password" 
                        className="text-input" 
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        disabled={isLoggedIn}
                      />
                    </div>

                    <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
                      {isLoggedIn ? (
                        <button type="button" className="btn rose" onClick={handleLogout}>
                          Log Out
                        </button>
                      ) : (
                        <button type="submit" className="btn primary">
                          Sign In
                        </button>
                      )}
                    </div>
                  </form>

                  {loginStatus && (
                    <div 
                      style={{ 
                        marginTop: '1.5rem', 
                        padding: '1rem', 
                        borderRadius: 'var(--border-radius-md)', 
                        background: 'var(--bg-secondary)',
                        border: '1px solid var(--card-border)',
                        fontWeight: '500'
                      }}
                    >
                      {loginStatus}
                    </div>
                  )}

                  {isLoggedIn && (
                    <div style={{ marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      <p>🟢 Logged in as: <strong style={{ color: 'var(--accent-cyan)' }}>{username}</strong></p>
                      <p>🪪 Profile ID: <strong style={{ color: 'var(--accent-cyan)' }}>{profileId}</strong></p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
};

export default App;
