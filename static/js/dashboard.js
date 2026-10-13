let allLatest=[];

async function loadDashboard(){
    try{
        const selectedYear=document.getElementById("yearSelect").value;
        const response=await fetch("/api/summary?ts="+Date.now());
        const data=await response.json();

        allLatest=data.all_latest || [];

        let rows=allLatest;
        if(selectedYear){
            const r=await fetch("/api/data?year="+encodeURIComponent(selectedYear)+"&ts="+Date.now());
            const j=await r.json();
            rows=j.records || [];
        }

        updateCards(data);
        drawTop(data.top10 || []);
        drawTrend(data.trend || []);
        drawMap(rows);
        drawDonut(rows);
        drawRange(rows);
        renderTable(rows);

        document.getElementById("statusText").textContent =
            data.live ? "Live Data" : "Preview Data";
        document.getElementById("statusDot").className =
            data.live ? "live" : "";

    }catch(e){
        console.error(e);
    }
}

function updateCards(data){
    document.getElementById("totalCountries").textContent=data.total_countries || 0;
    document.getElementById("average").textContent=(data.average || 0).toFixed(2)+"%";
    document.getElementById("highest").textContent=(data.highest || 0).toFixed(2)+"%";
    document.getElementById("lowest").textContent=(data.lowest || 0).toFixed(2)+"%";

    const top=(data.top10||[])[0];
    const bottom=(data.bottom5||[])[0];

    document.getElementById("highestCountry").textContent =
        top ? top.country+" ("+data.latest_year+")" : "Latest available year";
    document.getElementById("lowestCountry").textContent =
        bottom ? bottom.country+" ("+data.latest_year+")" : "Latest available year";
}

function plot(id, traces, layout){
    Plotly.react(id,traces,{
        ...layout,
        paper_bgcolor:"rgba(0,0,0,0)",
        plot_bgcolor:"rgba(0,0,0,0)",
        font:{family:"Segoe UI, Arial",color:"#27466f",size:10},
        margin:{l:42,r:12,t:12,b:48},
        showlegend:false
    },{responsive:true,displayModeBar:false});
}

function drawTop(rows){
    const r=rows.slice(0,10).reverse();
    plot("topChart",[{
        x:r.map(x=>x.percentage),
        y:r.map(x=>x.country),
        type:"bar",
        orientation:"h",
        text:r.map(x=>Number(x.percentage).toFixed(1)+"%"),
        textposition:"outside",
        hovertemplate:"%{y}<br>%{x:.2f}%<extra></extra>"
    }],{xaxis:{range:[0,105],title:"Percentage (%)",gridcolor:"#edf2f8"},
        yaxis:{automargin:true},height:310});
}

function drawTrend(rows){
    plot("trendChart",[{
        x:rows.map(x=>x.year),
        y:rows.map(x=>x.percentage),
        type:"scatter",
        mode:"lines+markers",
        line:{width:3},
        marker:{size:6},
        hovertemplate:"Year %{x}<br>Average %{y:.2f}%<extra></extra>"
    }],{xaxis:{title:"Year",gridcolor:"#edf2f8"},
        yaxis:{title:"Percentage (%)",gridcolor:"#edf2f8"},
        height:310});
}

function drawMap(rows){
    const valid=rows.filter(x=>x.country_code && x.country_code.length===3);
    plot("mapChart",[{
        type:"choropleth",
        locations:valid.map(x=>x.country_code),
        z:valid.map(x=>x.percentage),
        text:valid.map(x=>x.country),
        colorscale:"Blues",
        zmin:0,zmax:100,
        colorbar:{title:"%"},
        hovertemplate:"%{text}<br>%{z:.2f}%<extra></extra>"
    }],{geo:{showframe:false,showcoastlines:false,projection:{type:"natural earth"}},
        height:310});
}

function drawDonut(rows){
    const buckets=[0,0,0,0,0];
    rows.forEach(x=>{
        const v=Number(x.percentage);
        if(v<20)buckets[0]++;
        else if(v<40)buckets[1]++;
        else if(v<60)buckets[2]++;
        else if(v<80)buckets[3]++;
        else buckets[4]++;
    });
    plot("donutChart",[{
        labels:["0–19%","20–39%","40–59%","60–79%","80–100%"],
        values:buckets,
        type:"pie",
        hole:.58,
        textinfo:"percent"
    }],{height:310});
}

function drawRange(rows){
    const labels=["0–19","20–39","40–59","60–79","80–100"];
    const values=[0,0,0,0,0];
    rows.forEach(x=>{
        const v=Number(x.percentage);
        if(v<20)values[0]++;
        else if(v<40)values[1]++;
        else if(v<60)values[2]++;
        else if(v<80)values[3]++;
        else values[4]++;
    });
    plot("rangeChart",[{
        x:labels,y:values,type:"bar",
        text:values.map(String),textposition:"outside",
        hovertemplate:"%{x}%<br>%{y} countries<extra></extra>"
    }],{xaxis:{title:"Percentage range"},yaxis:{title:"Countries",gridcolor:"#edf2f8"},height:310});
}

function statusFor(v){
    if(v>=80)return ["Excellent","excellent"];
    if(v>=60)return ["Good","good"];
    return ["Needs Attention","moderate"];
}

function renderTable(rows=allLatest){
    const q=(document.getElementById("searchInput").value||"").toLowerCase();
    const filtered=rows.filter(x=>x.country.toLowerCase().includes(q))
        .sort((a,b)=>b.percentage-a.percentage)
        .slice(0,50);

    let html="";
    filtered.forEach((x,i)=>{
        const s=statusFor(Number(x.percentage));
        html+=`<tr>
        <td>${i+1}</td>
        <td>${x.country}</td>
        <td>${x.year}</td>
        <td><b>${Number(x.percentage).toFixed(2)}%</b></td>
        <td><span class="status ${s[1]}">${s[0]}</span></td>
        <td><button class="small-btn" onclick='viewDetails(${JSON.stringify(x)})'>View Details</button></td>
        </tr>`;
    });
    document.getElementById("dataTable").innerHTML=html ||
        `<tr><td colspan="6">No country found.</td></tr>`;
}

function viewDetails(x){
    alert(
        "Country: "+x.country+
        "\\nYear: "+x.year+
        "\\nFemale education/literacy: "+Number(x.percentage).toFixed(2)+"%"
    );
}

loadDashboard();
setInterval(loadDashboard, 5*60*1000);
