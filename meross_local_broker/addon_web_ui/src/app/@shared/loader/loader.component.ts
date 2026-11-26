import { Component, OnInit, Input, ChangeDetectionStrategy } from '@angular/core';

@Component({
  selector: 'app-loader',
  templateUrl: './loader.component.html',
  styleUrls: ['./loader.component.scss'],
  changeDetection: ChangeDetectionStrategy.Eager,
  standalone: false,
})
export class LoaderComponent implements OnInit {
  @Input() isLoading = false;
  @Input() size = 1;
  @Input() message: string | undefined;

  constructor() {}

  ngOnInit() {}
}
