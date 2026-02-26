function T_clean = clean_by_ssm(T, Map)
% CLEAN_BY_SSM
% For each variable listed in Map, use its SSM channel to replace
% invalid samples with the nearest valid sample in time.
%
% INPUTS:
%   T    : main data table. Must contain Time plus all variables + SSMs
%   Map  : table with columns:
%             Map.VarName     -> name of signal column in T (string/char)
%             Map.SSMName     -> name of SSM/status column in T (string/char)
%             Map.ValidValue  -> numeric code that means "valid"
%
% OUTPUT:
%   T_clean : same as T except mapped variables are "fixed"
%
% NOTES:
% - If a channel never has a valid SSM, we fill that channel with NaN.
%   You can change that behavior below if you prefer to leave it alone.

    T_clean = T;  % start with a copy

    nRows = height(T);
    all_idx = (1:nRows)';  % integer index for each timestep

    for k = 1:height(Map)

        varName    = Map.VarName{k};
        ssmName    = Map.SSMName{k};
        valid_code = Map.ValidValue(k);

        % Safety checks: skip if names aren't actually in T
        if ~ismember(varName, T.Properties.VariableNames)
            warning('Variable %s not found in T. Skipping.', varName);
            continue;
        end
        if ~ismember(ssmName, T.Properties.VariableNames)
            warning('SSM %s not found in T. Skipping %s.', ssmName, varName);
            continue;
        end

        % Pull data + ssm
        sig = T.(varName);
        ssm = T.(ssmName);

        % We assume sig is numeric. If it's not, we handle later.
        % Build mask of valid timesteps
        valid_mask = (ssm == valid_code);

        if all(~valid_mask)
            % No valid samples at ALL for this channel
            % -> Can't infer "good" data. Two common options:
            % Option A: nuke it to NaN (shown)
            % Option B: leave it alone (comment/uncomment below)
            sig_fixed = nan(size(sig));

            % Uncomment next line instead if you prefer "leave data untouched":
            % sig_fixed = sig;
        else
            % Get row indices of valid samples
            good_idx = all_idx(valid_mask);

            % For every row, find the nearest valid row index in time.
            % 'nearest' chooses whichever valid sample is closest in index (time step).
            % 'extrap' lets us extend the first/last valid sample outward.
            nearest_good_idx = interp1( ...
                good_idx, ...             % x data (known good positions)
                good_idx, ...             % y data (identity mapping)
                all_idx, ...              % query points (every row)
                'nearest', 'extrap');

            sig_fixed = sig;

            % Replace only the invalid rows with nearest valid value
            sig_fixed(~valid_mask) = sig(nearest_good_idx(~valid_mask));
        end

        % Write back into cleaned table
        T_clean.(varName) = sig_fixed;
    end
end
