function setGroup(g,on){var b=document.querySelectorAll('input[name=tool][data-g="'+g+'"]');
for(var i=0;i<b.length;i++){b[i].checked=on;}return false;}
function setAll(on){var b=document.querySelectorAll('input[name=tool]');
for(var i=0;i<b.length;i++){b[i].checked=on;}return false;}
function setLean(){var lean=window.LEAN_TOOLS||[];var s={};
for(var i=0;i<lean.length;i++){s[lean[i]]=1;}
var b=document.querySelectorAll('input[name=tool]');
for(var j=0;j<b.length;j++){b[j].checked=!!s[b[j].value];}
var d=document.querySelector('input[name=allow_destructive]');
if(d){d.checked=false;}return false;}
function filterTools(input){
var q=(input.value||'').trim().toLowerCase();
var groups=document.querySelectorAll('.tool-group');
for(var i=0;i<groups.length;i++){
var g=groups[i];var ls=g.querySelectorAll('label.tool');var shown=0;
for(var j=0;j<ls.length;j++){
var on=!q||ls[j].textContent.toLowerCase().indexOf(q)>-1;
ls[j].style.display=on?'':'none';if(on){shown++;}}
g.style.display=(!q||shown>0)?'':'none';
if(q&&shown>0){g.open=true;}}
}
function copyKey(){var el=document.getElementById('reveal-key');if(!el){return;}
var t=el.textContent;
if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t);}
else{var ta=document.createElement('textarea');ta.value=t;document.body.appendChild(ta);ta.select();
try{document.execCommand('copy');}catch(e){}document.body.removeChild(ta);}}
