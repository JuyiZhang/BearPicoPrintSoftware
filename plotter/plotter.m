% filepath: /Users/arkr/Documents/Coursework/SP 2025/Capstone/BearPicoPrintSoftware/plotter/plotter.m
% Read the CSV file into a table (ignoring comment lines)
tbl = readtable('data.csv', 'Delimiter', 'comma');

% Filter out rows with invalid data based on the Validity column
validRows = strcmp(tbl.Validity, 'Valid');
validTbl = tbl(validRows, :);

% Directly convert the table into separate variables
x = validTbl.Amplitude;
y = validTbl.Frequency;
z = validTbl.Diameter;

% Define a grid for interpolation
xq = linspace(min(x), max(x), 50);
yq = linspace(min(y), max(y), 50);
[Xq, Yq] = meshgrid(xq, yq);

% Interpolate data from the scattered points onto the grid
Zq = griddata(x, y, z, Xq, Yq, 'cubic');

% Create a surface plot
figure;
surf(Xq, Yq, Zq);
colormap jet;
shading interp;
xlabel('Amplitude');
ylabel('Frequency');
zlabel('Diameter');
title('Surface Plot of Amplitude, Frequency, and Diameter');
colorbar;
rotate3d on;  % Enable interactive 3D rotation