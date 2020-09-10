function ExportXPNotes(fileName, fileDir)
% fileDir='cd';
% fileName='Experiment Note Sheet - example.xlsx';
%% Convert notes spreadsheet to json file

%% First read header
opts = spreadsheetImportOptions("NumVariables", 11);
opts.DataRange = "A2:K2";
opts.VariableNames = ["SubjectID", "VarName2", "VarName3", "VarName4", "VarName5", "Goal", "Type", "Sex", "DOB", "Tag", "Cagecard"];
opts.VariableTypes = ["char", "double", "double", "double", "double", "char", "char", "char", "datetime", "categorical", "double"];
opts.MissingRule = "omitvar";
opts = setvaropts(opts, ["SubjectID", "Goal", "Type", "Sex"], "WhitespaceRule", "preserve");
opts = setvaropts(opts, ["SubjectID", "Goal", "Type", "Sex", "Tag"], "EmptyFieldRule", "auto");
opts = setvaropts(opts, ["VarName2", "VarName3", "Cagecard", "DOB"], "TreatAsMissing", '');
opts = setvaropts(opts, "DOB", "InputFormat", "MM/dd/uu");

% Import data
xpNotesHeader = readtable(fullfile(fileDir, fileName), opts, "UseExcel", false);

clear opts

%% Now read experiment notes
opts = spreadsheetImportOptions("NumVariables", 10);
opts.DataRange = 5; % Starting at row 5
opts.VariableNames = ["Procedure", "Date", "APcoord", "MLcoord", "Depth", "Notes", "StimPower", "StimFreq", "PulseDur", "Device", "Comments"];
opts.VariableTypes = ["categorical", "datetime", "double", "double", "double", "string", "double", "double", "double", "categorical", "string"];
opts = setvaropts(opts, ["Notes", "Comments"], "WhitespaceRule", "preserve");
opts = setvaropts(opts, ["Procedure", "Notes", "Device", "Comments"], "EmptyFieldRule", "auto");
opts = setvaropts(opts, "Date", "InputFormat", "MM/dd/uu");

% Import  data
xpNotes = readtable(fullfile(fileDir, fileName), opts, "UseExcel", false);

% Note on coordinates:
% AP: anterior is positive
% ML: right is positive 
% DV: dorsal is positive (add - to notes)

%% Write notes to json file
% adjust variables
xpNotesHeader.Cagecard=num2str(xpNotesHeader.Cagecard);
if xpNotesHeader.DOB < '01-Jan-2015'; xpNotesHeader.DOB(1)=''; end
if nanmean(xpNotes.Depth)>0; xpNotes.Depth=-xpNotes.Depth; end

% find procedures and sessions 
procedureIdx=~isundefined(xpNotes.Procedure);
sessionIdx=xpNotes.Procedure=='R'; % Ephys recordings should be noted as R
procedureIdx=find(procedureIdx & ~sessionIdx);
sessionIdx=find(sessionIdx);
if ~isempty(sessionIdx)
    sessions=struct('baseName',[],'date',[],'probe',[],'adapter',[],'AP',[],'ML',[],'depth',[],...
        'stimPower',[],'stimFreq',[],'pulseDur',[],'stimDevice',[]);
end

% open file
fid  = fopen(fullfile(fileDir,[char(xpNotesHeader.SubjectID) '_notes.json']),'w');
fprintf(fid,'{\r\n');

% first print header variables
fprintf(fid,'\t"Header": {\r\n');
str=strrep(jsonencode(xpNotesHeader),',"',sprintf(',\r\n\t\t"'));
fprintf(fid,'%s%s%s',sprintf('\t\t'), str(3:end-2), sprintf('\r\n\t},\r\n'));

% then print notes
procedureRange=[];
fprintf(fid,'\t"Procedures": [\r\n');
for procNum=1:numel(procedureIdx)
    if any(ismember(procedureRange,procedureIdx(procNum)))
        continue
    end
    % find row range of procedure
    % Special procedures for injections and fiber optic implantation
    if ismember(xpNotes.Procedure(procedureIdx(procNum)),{'injection','implant FO'})
        specProcIdx=procedureIdx(...
        ~contains(string(xpNotes.Procedure(procedureIdx)),{'injection','fiber optic'}));
        procedureRange=procedureIdx(procNum):...
            specProcIdx(find(specProcIdx>procedureIdx(procNum),1))-1;
    else
        if procNum<numel(procedureIdx)
            procedureRange=procedureIdx(procNum):procedureIdx(procNum+1)-1;
        else
            procedureRange=procedureIdx(procNum):numel(xpNotes.Procedure);
        end
    end
    % print procedure type, date and head comment
    procedureInfo=strrep(jsonencode(xpNotes(procedureIdx(procNum),[1,2,6])),',"',sprintf(',\r\n\t\t"'));
    fprintf(fid,'\t\t%s',procedureInfo(2:end-2));

    % if there are other notes, add them
    if numel(procedureRange)>1 
        % There are notes associated with the procedure.
        % Two cases: 
        %   1/ any procedure listed above, excluding recordings
        if any(ismember(procedureIdx,procedureRange(2:end))) 
            fprintf(fid,',\r\n\t\t"Subprocedures": [\r\n');
            subprocIdx=procedureIdx(ismember(procedureIdx,procedureRange(2:end)));
            for subprocNum=1:numel(subprocIdx)               
                subprocedureInfo=strrep(jsonencode(xpNotes(subprocIdx(subprocNum),...
                    [1,3:6])),',"',sprintf(',\r\n\t\t\t\t"'));
                fprintf(fid,'\t\t\t\t%s',subprocedureInfo(2:end-2));
                
                if subprocNum<numel(subprocIdx)
                    subprocRange=subprocIdx(subprocNum+1)-1;
                else
                    subprocRange=procedureIdx(find(procedureIdx>subprocIdx(end),1))-1;
                end
                
                notes=xpNotes.Notes(subprocIdx(subprocNum)+1:subprocRange);
                notes=[notes{:}];
                if ~isempty(notes)
                    fprintf(fid,[',\r\n\t\t\t\t"Extended Notes": "%s"'],notes);
                end
                fprintf(fid,'\r\n\t\t\t\t}');
                if subprocNum<numel(subprocIdx); fprintf(fid,',\r\n'); end
            end
            fprintf(fid,'\r\n\t\t\t]\r\n');
            
        %   2/ recordings (aka sessions in the pipeline, that groups 
        %       ephys, video and other concurrent recordings together)
        else
            recMark=xpNotes.Procedure(procedureRange(2:end));
            recMark(isundefined(recMark))=('-'); recMark=string(recMark);
            depth=xpNotes.Depth(procedureRange(2:end));
            depthstr=string(depth); depthstr(isnan(depth))='    ';
            notes=xpNotes.Notes(procedureRange(2:end));
            % join notes
            notes=strjoin(recMark + sprintf('\t') + depthstr + sprintf(""":\t""") + notes,...
                '",\r\n\t\t\t"'); %[notes{:}];
            fprintf(fid,',\r\n\t\t"Extended Notes":{\r\n\t\t\t"%s"}\r\n',notes);
        end     
        %% get info about sessions
        % a group of sessions from the same day is called a setlist and
        % will have the same date
        if any(ismember(sessionIdx,procedureRange(2:end)))
            sessionIds=find(ismember(sessionIdx,procedureRange(2:end)));
            for sessionnNum=1:numel(sessionIds) 
                sessions(sessionIds(sessionnNum)).baseName=[...
                    xpNotesHeader.SubjectID{1} '_',...
                    char(datetime(xpNotes.Date(procedureIdx(procNum)),'Format','MMdd')) '_'...
                    num2str(-xpNotes.Depth(sessionIdx(sessionIds(sessionnNum))))];
                sessions(sessionIds(sessionnNum)).date=xpNotes.Date(procedureIdx(procNum));
                recNotes=xpNotes.Notes(procedureIdx(procNum));
                sessions(sessionIds(sessionnNum)).probe=regexp(recNotes,'.+(?= &)','match','once');
                sessions(sessionIds(sessionnNum)).adapter=regexp(recNotes,'(?<=& ).+','match','once');
                sessions(sessionIds(sessionnNum)).AP=xpNotes.APcoord(sessionIdx(sessionIds(sessionnNum)));
                sessions(sessionIds(sessionnNum)).ML=xpNotes.MLcoord(sessionIdx(sessionIds(sessionnNum)));
                sessions(sessionIds(sessionnNum)).depth=xpNotes.Depth(sessionIdx(sessionIds(sessionnNum)));
                sessions(sessionIds(sessionnNum)).stimPower=xpNotes.StimPower(sessionIdx(sessionIds(sessionnNum)));
                sessions(sessionIds(sessionnNum)).stimFreq=xpNotes.StimFreq(sessionIdx(sessionIds(sessionnNum)));
                sessions(sessionIds(sessionnNum)).pulseDur=xpNotes.PulseDur(sessionIdx(sessionIds(sessionnNum)));
                sessions(sessionIds(sessionnNum)).stimDevice=xpNotes.Device(sessionIdx(sessionIds(sessionnNum)));            
            end
        end
    else
        fprintf(fid,'\r\n');
    end
    if procNum<numel(procedureIdx)
        fprintf(fid,'\t\t},\r\n');
    else
        fprintf(fid,'\t\t}\r\n');
    end
end
% close Procedures list
fprintf(fid,'\t],\r\n');
 
%% Write down Sessions
if exist('sessions','var')
    fprintf(fid,'\t"Sessions": [ \r\n');
    str=strrep(jsonencode(sessions),',"',sprintf(',\r\n\t\t"'));
    str=strrep(str,'},{',sprintf('\r\n\t\t},\r\n\t\t{'));
    fprintf(fid,'%s%s%s',sprintf('\t\t'), str(2:end-1), sprintf('\r\n\t]\r\n'));
end
%close file
fprintf(fid,'}');
fclose(fid);

